# Copyright 2016, FBPIC contributors
# Authors: Remi Lehe, Manuel Kirchen
# License: 3-Clause-BSD-LBNL
"""
This test file is part of FB-PIC (Fourier-Bessel Particle-In-Cell).

It tests the structures implemented in fields.py,
by studying the propagation of a laser in vacuum:
- The mode 0 is tested by using a linearly polarized gaussian beam,
   which propagates to the right.
- The mode 1 is tested by using a linearly-polarized Laguerre-Gauss beam

In both cases, the evolution of the a0 and w0 are compared
with theoretical results from diffraction theory.

These tests are performed in 3 cases:
- Periodic box : in this case, a very large timestep is taken,
  so as to test the absence of a Courant condition
- Moving window : in this case, the timestep has to be reduced,
  in order to leave time for the moving window to shift/damp the fields

Usage :
-------
In order to show the images of the laser, and manually check the
agreement between the simulation and the theory:
$ python tests/test_laser_envelope.py
(except when setting show to False in the parameters below)

"""
import numpy as np
from scipy.constants import c
from scipy.optimize import curve_fit
from fbpic.main import Simulation
from fbpic.lpa_utils.laser import add_laser_pulse, \
    GaussianLaser, LaguerreGaussLaser, DonutLikeLaguerreGaussLaser

# Parameters
# ----------
# (See the documentation of the function propagate_pulse
# below for their definition)
show = False # Whether to show the plots, and check them manually

use_cuda = False

# Simulation box
Nz = 80
zmin = -10.e-6
zmax = 10.e-6
Nr = 25
Lr = 40.e-6
Nm = 2
n_order = -1
# Laser pulse
w0 = 4.e-6
ctau = 5.e-6
k0 = 2*np.pi/0.8e-6
a0 = 1.
# Propagation
L_prop = 30.e-6
zf = 25.e-6
N_diag = 10   # Number of diagnostic points along the propagation
# Checking the results
N_show = 2
rtol = 1.e-4

def test_laser_periodic(show=False):
    """
    Function that is run by py.test, when doing `python setup.py test`
    Test the propagation of a laser in a periodic box.
    """
    # Choose the regular timestep, not an arbitrarily long timestep
    # (because the envelope uses dta, which might not fit inside the window)
    dt = (zmax-zmin)*1./c/Nz
    dt = L_prop*1./c/N_diag
    # Test modes up to m=1
    for m in [-1, 0, 1]:

        print('')
        print('Testing mode m=%d' %m)
        propagate_pulse( Nz, Nr, abs(m)+1, zmin, zmax, Lr, L_prop, zf, dt,
                          N_diag, w0, ctau, k0, a0, m, N_show, n_order,
                          rtol, boundaries='periodic', v_window=0, show=show )

    print('')

def test_laser_moving_window(show=False):
    """
    Function that is run by py.test, when doing `python setup.py test`
    Test the propagation of a laser in a moving window
    """
    # Choose the regular timestep (required by moving window)
    dt = (zmax-zmin)*1./c/Nz
    # Test modes up to m=1
    for m in [-1, 0, 1]:

        print('')
        print('Testing mode m=%d' %m)
        propagate_pulse( Nz, Nr, abs(m)+1, zmin, zmax, Lr, L_prop, zf, dt,
                          N_diag, w0, ctau, k0, a0, m, N_show, n_order,
                          rtol, boundaries='open', v_window=c, show=show )

    print('')


def propagate_pulse( Nz, Nr, Nm, zmin, zmax, Lr, L_prop, zf, dt,
        N_diag, w0, ctau, k0, a0, m, N_show, n_order, rtol,
        boundaries, v_window=0, use_galilean=False, v_comoving=0, show=False ):
    """
    Propagate the beam over a distance L_prop in Nt steps,
    and extracts the waist and a0 at each step.

    Parameters
    ----------
    show : bool
       Wether to show the fields, so that the user can manually check
       the agreement with the theory.
       If True, this will periodically show the map of the fields (with
       a period N_show), as well as (eventually) the evoluation of a0 and w0.
       If False, this

    N_diag : int
       Number of diagnostic points (i.e. measure of waist and a0)
       along the propagation

    Nz, Nr : int
       The number of points on the grid in z and r respectively

    Nm : int
        The number of modes in the azimuthal direction

    zmin, zmax : float
        The limits of the box in z

    Lr : float
       The size of the box in the r direction
       (In the case of Lr, this is the distance from the *axis*
       to the outer boundary)

    L_prop : float
       The total propagation distance (in meters)

    zf : float
       The position of the focal plane of the laser (only works for m=1)

    dt : float
       The timestep of the simulation

    w0 : float
       The initial waist of the laser (in meters)

    ctau : float
       The initial temporal waist of the laser (in meters)

    k0 : flat
       The central wavevector of the laser (in meters^-1)

    a0 : float
       The initial a0 of the pulse

    m : int
       Index of the mode to be tested
       For m = 1 : test with a gaussian, linearly polarized beam
       For m = 0 : test with an annular beam, polarized in E_theta

    n_order : int
       Order of the stencil

    rtol : float
       Relative precision with which the results are tested

    boundaries : string
        Type of boundary condition
        Either 'open' or 'periodic'

    v_window : float
        Speed of the moving window

    v_comoving : float
        Velocity at which the currents are assumed to move

    use_galilean: bool
        Whether to use a galilean frame that moves at the speed v_comoving

    Returns
    -------
    A dictionary containing :
    - 'a' : 1d array containing the values of the amplitude
    - 'w' : 1d array containing the values of waist
    - 'fld' : the Fields object at the end of the simulation.
    """

    # Initialize the simulation object
    sim = Simulation( Nz, zmax, Nr, Lr, Nm, dt, p_zmin=0, p_zmax=0,
                    p_rmin=0, p_rmax=0, p_nz=2, p_nr=2, p_nt=2, n_e=0.,
                    n_order=n_order, zmin=zmin, use_cuda=use_cuda,
                    boundaries=boundaries, v_comoving=v_comoving,
                    exchange_period = 1, use_galilean=use_galilean,
                    use_envelope = True )
    # Remove the particles
    sim.ptcl = []
    # Set the moving window object
    if v_window !=0:
        sim.set_moving_window( v=v_window )

    # Initialize the laser fields
    z0 = (zmax+zmin)/2
    init_fields( sim, w0, ctau, k0, z0, zf, a0, m )

    # Create the arrays to get the waist and amplitude
    w = np.zeros(N_diag)
    a = np.zeros(N_diag)

    # Calculate the number of steps to run between each diagnostic
    Ntot_step = int( round( L_prop/(c*dt) ) )
    N_step = int( round( Ntot_step/N_diag ) )

    dz = sim.fld.interp[0].dz

    # Loop over the iterations
    print('Running the simulation...')
    for it in range(N_diag) :
        print( 'Diagnostic point %d/%d' %(it, N_diag) )

        #Obtain values of zmin and Nz including the guard regions
        zmin, Nz = sim.fld.zmin, sim.fld.Nz
        # Obtain the index of the center of the beam
        izref = int( (z0 + it * N_step * (c - v_window) * dt - zmin) / dz ) % Nz
        # Fit the fields to find the waist and a0
        w[it], a[it] = fit_fields( sim.fld, m, izref )
        # Plot the fields during the simulation
        if show==True and it%N_show == 0 :
            show_fields(sim.fld.envelope_interp[m], 'a')

        # Advance the Maxwell equations
        sim.step( N_step, show_progress= False )

    # Get the analytical solution
    z_prop = c*dt*N_step*np.arange(N_diag)
    ZR = 0.5*k0*w0**2
    w_analytic = w0*np.sqrt( 1 + (z_prop-zf)**2/ZR**2 )
    a_analytic = a0 /( 1 + (z_prop-zf)**2/ZR**2 )**(1./2)

    # Either plot the results and check them manually
    if show is True:
        import matplotlib.pyplot as plt
        plt.suptitle('Diffraction of a pulse in the mode %d' %m)
        plt.subplot(121)
        plt.plot( 1.e6*z_prop, 1.e6*w, 'o', label='Simulation' )
        plt.plot( 1.e6*z_prop, 1.e6*w_analytic, '--', label='Theory' )
        plt.xlabel('z (microns)')
        plt.ylabel('w (microns)')
        plt.title('Waist')
        plt.legend(loc=0)
        plt.subplot(122)
        plt.plot( 1.e6*z_prop, a, 'o', label='Simulation' )
        plt.plot( 1.e6*z_prop, a_analytic, '--', label='Theory' )
        plt.xlabel('z (microns)')
        plt.ylabel('a')
        plt.legend(loc=0)
        plt.title('Amplitude')
        plt.show()
    # or automatically check that the theoretical and simulated curves
    # of w and A are close
    else:
        assert np.allclose( w, w_analytic, rtol=rtol )
        assert np.allclose( a, a_analytic, rtol=10.e-3 )
        print('The simulation results agree with the theory to %e.' %rtol)

    # Return a dictionary of the results
    return( { 'a' : a, 'w' : w, 'fld' : sim.fld } )


def init_fields( sim, w, ctau, k0, z0, zf, a0, m=1 ) :
    """
    Imprints the appropriate profile on the fields of the simulation.

    Parameters
    ----------
    sim: Simulation object from fbpic

    w : float
       The initial waist of the laser (in microns)

    ctau : float
       The initial temporal waist of the laser (in microns)

    k0 : flat
       The central wavevector of the laser (in microns^-1)

    z0 : float
       The position of the centroid on the z axis

    zf : float
       The position of the focal plane

    a0 : float
       The initial a0 of the pulse

    m: int, optional
        The mode on which to imprint the profile
        For m = 0 : gaussian profile, linearly polarized beam
        For m = 1 : annular profile
    """
    # Initialize the fields

    tau = ctau/c
    lambda0 = 2*np.pi/k0
    # Create the relevant laser profile

    if m == 0:
        profile = GaussianLaser( a0=a0, waist=w, tau=tau,
                    lambda0=lambda0, z0=z0, zf=zf )
    elif m == 1:
        profile = LaguerreGaussLaser( 0, 1, a0=a0, waist=w, tau=tau,
                    lambda0=lambda0, z0=z0, zf=zf )
    elif m == -1:
        profile = DonutLikeLaguerreGaussLaser( 0, -1, a0=a0/2**.5,
                    waist=w, tau=tau, lambda0=lambda0, z0=z0, zf=zf )

    # Add the profiles to the simulation
    add_laser_pulse( sim, profile, method = 'direct_envelope' )

def gaussian_transverse_profile( r, w, a) :
    """
    Calculte the Gaussian transverse profile.

    This is used for the fit of the fields

    Parameters
    ----------
    r: 1darray
       Represents the positions of the grid in r

    w : float
       The initial waist of the laser (in microns)

    a : float
       The a0 of the pulse
    """
    return( a*np.exp( -r**2/w**2 ) )

def annular_transverse_profile( r, w, a ) :
    """
    Calculte the annular transverse profile.

    This is used both for the initialization and
    for the fit of the fields

    Parameters
    ----------
    r: 1darray
       Represents the positions of the grid in r

    w : float
       The initial waist of the laser (in microns)

    a : float
       The a0 of the pulse
    """
    return( a*(r/w)*np.exp( -r**2/w**2 ) )

def fit_fields( fld, m, izref ) :
    """
    Extracts the waist and a0 of the pulse through a transverse Gaussian fit.

    The laser oscillations are first averaged longitudinally.

    Parameters
    ----------
    fld : Fields object from fbpic

    m : int, optional
       The index of the mode to be fitted

    izref : int
        The indice at which the center of the beam is located
    """
    laser_profile = abs( fld.envelope_interp[m].a[izref] )
    # Do the fit
    r = fld.interp[m].r
    if m==0 :  # Gaussian profile
        fit_result = curve_fit(gaussian_transverse_profile, r,
                            laser_profile, p0=np.array([w0,a0]) )
    else: # Annular profile, or Laguerre-Gaussian profile
        fit_result = curve_fit(annular_transverse_profile, r,
                            laser_profile, p0=np.array([w0,a0]) )

    return( fit_result[0] )

def show_fields( grid, fieldtype ):
    """
    Show the field `fieldtype` on the interpolation grid

    Parameters
    ----------
    grid: an instance of FieldInterpolationGrid
        Contains the field on the interpolation grid for
        on particular azimuthal mode

    fieldtype : string
        Name of the field to be plotted.
        (either 'Er', 'Et', 'Ez', 'Br', 'Bt', 'Bz',
        'Jr', 'Jt', 'Jz', 'rho')
    """
    # matplotlib only needs to be imported if this function is called
    import matplotlib.pyplot as plt

    # Select the field to plot
    plotted_field = getattr( grid, fieldtype)
    # Show the field also below the axis for a more realistic picture
    plotted_field = np.hstack( (plotted_field[:,::-1],plotted_field) )
    extent = 1.e6*np.array([grid.zmin, grid.zmax, -grid.rmax, grid.rmax])
    plt.clf()
    plt.suptitle('%s, for mode %d' %(fieldtype, grid.m) )

    # Plot the real part
    plt.subplot(211)
    plt.imshow( plotted_field.real.T[::-1], aspect='auto',
                interpolation='nearest', extent=extent )
                #interpolation='nearest')
    plt.xlabel('z')
    plt.ylabel('r')
    cb = plt.colorbar()
    cb.set_label('Real part')

    # Plot the imaginary part
    plt.subplot(212)
    plt.imshow( plotted_field.imag.T[::-1], aspect='auto',
                interpolation='nearest', extent = extent )
                #interpolation='nearest')
    plt.xlabel('z')
    plt.ylabel('r')
    cb = plt.colorbar()
    cb.set_label('Imaginary part')

    plt.show()

if __name__ == '__main__' :

    # Run the testing function
    test_laser_periodic(show=show)

    test_laser_moving_window(show=show)
