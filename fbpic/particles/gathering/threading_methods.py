# Copyright 2016, FBPIC contributors
# Authors: Remi Lehe, Manuel Kirchen, Kevin Peters
# License: 3-Clause-BSD-LBNL
"""
This file is part of the Fourier-Bessel Particle-In-Cell code (FB-PIC)
It defines the field gathering methods linear and cubic order shapes
on the CPU with threading.
"""
import numba
from numba import int64
from fbpic.utils.threading import njit_parallel, prange
import math
import numpy as np
# Import inline functions
from .inline_functions import \
    add_linear_gather_for_mode, add_cubic_gather_for_mode, \
    add_linear_envelope_gather_for_mode, add_cubic_envelope_gather_for_mode
# Compile the inline functions for CPU
add_linear_gather_for_mode = numba.njit( add_linear_gather_for_mode )
add_cubic_gather_for_mode = numba.njit( add_cubic_gather_for_mode )
add_linear_envelope_gather_for_mode = numba.njit(
                                        add_linear_envelope_gather_for_mode )
add_cubic_envelope_gather_for_mode = numba.njit(
                                        add_cubic_envelope_gather_for_mode )

# -----------------------
# Field gathering linear
# -----------------------

@njit_parallel
def gather_field_numba_linear(x, y, z,
                    invdz, zmin, Nz,
                    invdr, rmin, Nr,
                    Er_m0, Et_m0, Ez_m0,
                    Er_m1, Et_m1, Ez_m1,
                    Br_m0, Bt_m0, Bz_m0,
                    Br_m1, Bt_m1, Bz_m1,
                    Ex, Ey, Ez,
                    Bx, By, Bz ):
    """
    Gathering of the fields (E and B) using numba with multi-threading.
    Iterates over the particles, calculates the weighted amount
    of fields acting on each particle based on its shape (linear).
    Fields are gathered in cylindrical coordinates and then
    transformed to cartesian coordinates.
    Supports only mode 0 and 1.

    Parameters
    ----------
    x, y, z : 1darray of floats (in meters)
        The position of the particles

    invdz, invdr : float (in meters^-1)
        Inverse of the grid step along the considered direction

    zmin, rmin : float (in meters)
        Position of the edge of the simulation box along the
        direction considered

    Nz, Nr : int
        Number of gridpoints along the considered direction

    Er_m0, Et_m0, Ez_m0 : 2darray of complexs
        The electric fields on the interpolation grid for the mode 0

    Er_m1, Et_m1, Ez_m1 : 2darray of complexs
        The electric fields on the interpolation grid for the mode 1

    Br_m0, Bt_m0, Bz_m0 : 2darray of complexs
        The magnetic fields on the interpolation grid for the mode 0

    Br_m1, Bt_m1, Bz_m1 : 2darray of complexs
        The magnetic fields on the interpolation grid for the mode 1

    Ex, Ey, Ez : 1darray of floats
        The electric fields acting on the particles
        (is modified by this function)

    Bx, By, Bz : 1darray of floats
        The magnetic fields acting on the particles
        (is modified by this function)
    """
    # Deposit the field per cell in parallel
    for i in prange(x.shape[0]):
        # Preliminary arrays for the cylindrical conversion
        # --------------------------------------------
        # Position
        xj = x[i]
        yj = y[i]
        zj = z[i]

        # Cylindrical conversion
        rj = math.sqrt( xj**2 + yj**2 )
        if (rj !=0. ) :
            invr = 1./rj
            cos = xj*invr  # Cosine
            sin = yj*invr  # Sine
        else :
            cos = 1.
            sin = 0.
        exptheta_m0 = 1.
        exptheta_m1 = cos - 1.j*sin

        # Get linear weights for the deposition
        # -------------------------------------
        # Positions of the particles, in the cell unit
        r_cell =  invdr*(rj - rmin) - 0.5
        z_cell =  invdz*(zj - zmin) - 0.5
        # Original index of the uppper and lower cell
        ir_lower = int(math.floor( r_cell ))
        ir_upper = ir_lower + 1
        iz_lower = int(math.floor( z_cell ))
        iz_upper = iz_lower + 1
        # Linear weight
        Sr_lower = ir_upper - r_cell
        Sr_upper = r_cell - ir_lower
        Sz_lower = iz_upper - z_cell
        Sz_upper = z_cell - iz_lower
        # Set guard weights to zero
        Sr_guard = 0.

        # Treat the boundary conditions
        # -----------------------------
        # guard cells in lower r
        if ir_lower < 0:
            Sr_guard = Sr_lower
            Sr_lower = 0.
            ir_lower = 0
        # absorbing in upper r
        if ir_lower > Nr-1:
            ir_lower = Nr-1
        if ir_upper > Nr-1:
            ir_upper = Nr-1
        # periodic boundaries in z
        # lower z boundaries
        if iz_lower < 0:
            iz_lower += Nz
        if iz_upper < 0:
            iz_upper += Nz
        # upper z boundaries
        if iz_lower > Nz-1:
            iz_lower -= Nz
        if iz_upper > Nz-1:
            iz_upper -= Nz

        # Precalculate Shapes
        S_ll = Sz_lower*Sr_lower
        S_lu = Sz_lower*Sr_upper
        S_ul = Sz_upper*Sr_lower
        S_uu = Sz_upper*Sr_upper
        S_lg = Sz_lower*Sr_guard
        S_ug = Sz_upper*Sr_guard

        # E-Field
        # -------
        Fr = 0.
        Ft = 0.
        Fz = 0.
        # Add contribution from mode 0
        Fr, Ft, Fz = add_linear_gather_for_mode( 0,
            Fr, Ft, Fz, exptheta_m0, Er_m0, Et_m0, Ez_m0,
            iz_lower, iz_upper, ir_lower, ir_upper,
            S_ll, S_lu, S_lg, S_ul, S_uu, S_ug )
        # Add contribution from mode 1
        Fr, Ft, Fz = add_linear_gather_for_mode( 1,
            Fr, Ft, Fz, exptheta_m1, Er_m1, Et_m1, Ez_m1,
            iz_lower, iz_upper, ir_lower, ir_upper,
            S_ll, S_lu, S_lg, S_ul, S_uu, S_ug )
        # Convert to Cartesian coordinates
        # and write to particle field arrays
        Ex[i] = cos*Fr - sin*Ft
        Ey[i] = sin*Fr + cos*Ft
        Ez[i] = Fz

        # B-Field
        # -------
        # Clear the placeholders for the
        # gathered field for each coordinate
        Fr = 0.
        Ft = 0.
        Fz = 0.
        # Add contribution from mode 0
        Fr, Ft, Fz = add_linear_gather_for_mode( 0,
            Fr, Ft, Fz, exptheta_m0, Br_m0, Bt_m0, Bz_m0,
            iz_lower, iz_upper, ir_lower, ir_upper,
            S_ll, S_lu, S_lg, S_ul, S_uu, S_ug )
        # Add contribution from mode 1
        Fr, Ft, Fz = add_linear_gather_for_mode( 1,
            Fr, Ft, Fz, exptheta_m1, Br_m1, Bt_m1, Bz_m1,
            iz_lower, iz_upper, ir_lower, ir_upper,
            S_ll, S_lu, S_lg, S_ul, S_uu, S_ug )
        # Convert to Cartesian coordinates
        # and write to particle field arrays
        Bx[i] = cos*Fr - sin*Ft
        By[i] = sin*Fr + cos*Ft
        Bz[i] = Fz

    return Ex, Ey, Ez, Bx, By, Bz

@numba.njit
def gather_envelope_field_numba_linear(x, y, z,
                    invdz, zmin, Nz,
                    invdr, rmin, Nr, dt,
                    a_tuple, grad_a_r_tuple, grad_a_t_tuple, grad_a_z_tuple,
                    dta_tuple, m_tuple,
                    a2, grad_a2_x, grad_a2_y, grad_a2_z, a2_delayed,
                    averaging = False):
    """
    Gathering of the fields a and grad_a using numba with multi-threading.
    Iterates over the particles, calculates the weighted amount
    of fields acting on each particle based on its shape (linear).
    Fields are gathered in cylindrical coordinates and then
    transformed to cartesian coordinates.

    Parameters
    ----------
    x, y, z : 1darray of floats (in meters)
        The position of the particles

    invdz, invdr : float (in meters^-1)
        Inverse of the grid step along the considered direction

    zmin, rmin : float (in meters)
        Position of the edge of the simulation box along the
        direction considered

    Nz, Nr : int
        Number of gridpoints along the considered direction

    a_tuple, grad_a_r_tuple, grad_a_t_tuple, grad_a_z_tuple :
        tuple of 2darray of complexs
        The relevant fields on the interpolation grid for all the different modes

    m: tuple
        Indices of the azimuthal mode

    a, grad_a_x, grad_a_y, grad_a_z : 1darray of floats
        The relevant fields acting on the particles
        (is modified by this function)

    averaging : boolean, optional
        Whether to average the new values with the old ones or to
        discard the old values.

    """
    # Deposit the field per cell in parallel
    for i in range(x.shape[0]):
        # Preliminary arrays for the cylindrical conversion
        # --------------------------------------------
        # Position
        xj = x[i]
        yj = y[i]
        zj = z[i]

        # Cylindrical conversion
        rj = math.sqrt( xj**2 + yj**2 )
        if (rj !=0. ) :
            invr = 1./rj
            cos = xj*invr  # Cosine
            sin = yj*invr  # Sine
        else :
            cos = 1.
            sin = 0.

        # Get linear weights for the deposition
        # -------------------------------------
        # Positions of the particles, in the cell unit
        r_cell =  invdr*(rj - rmin) - 0.5
        z_cell =  invdz*(zj - zmin) - 0.5
        # Original index of the uppper and lower cell
        ir_lower = int(math.floor( r_cell ))
        ir_upper = ir_lower + 1
        iz_lower = int(math.floor( z_cell ))
        iz_upper = iz_lower + 1
        # Linear weight
        Sr_lower = ir_upper - r_cell
        Sr_upper = r_cell - ir_lower
        Sz_lower = iz_upper - z_cell
        Sz_upper = z_cell - iz_lower
        # Set guard weights to zero
        Sr_guard = 0.

        # Treat the boundary conditions
        # -----------------------------
        # guard cells in lower r
        if ir_lower < 0:
            Sr_guard = Sr_lower
            Sr_lower = 0.
            ir_lower = 0
        # absorbing in upper r
        if ir_lower > Nr-1:
            ir_lower = Nr-1
        if ir_upper > Nr-1:
            ir_upper = Nr-1
        # periodic boundaries in z
        # lower z boundaries
        if iz_lower < 0:
            iz_lower += Nz
        if iz_upper < 0:
            iz_upper += Nz
        # upper z boundaries
        if iz_lower > Nz-1:
            iz_lower -= Nz
        if iz_upper > Nz-1:
            iz_upper -= Nz

        # Precalculate Shapes
        S_ll = Sz_lower*Sr_lower
        S_lu = Sz_lower*Sr_upper
        S_ul = Sz_upper*Sr_lower
        S_uu = Sz_upper*Sr_upper
        S_lg = Sz_lower*Sr_guard
        S_ug = Sz_upper*Sr_guard
        # Envelope field
        # -------
        F = 0
        Fr = 0.
        Ft = 0.
        Fz = 0.
        dtF = 0.
        for it in range(len(m_tuple)):
            m = m_tuple[it]
            a_m = a_tuple[it]
            grad_a_r_m = grad_a_r_tuple[it]
            grad_a_t_m = grad_a_t_tuple[it]
            grad_a_z_m = grad_a_z_tuple[it]
            dta_m = dta_tuple[it]
            exptheta_m = (cos - 1.j*sin)**m
            # Add contribution from mode m
            F, Fr, Ft, Fz, dtF = add_linear_envelope_gather_for_mode( m, F, Fr,
                                Ft, Fz, dtF, exptheta_m,
                                a_m, grad_a_r_m, grad_a_t_m, grad_a_z_m, dta_m,
                                iz_lower, iz_upper, ir_lower,
                                ir_upper, S_ll, S_lu, S_lg, S_ul, S_uu, S_ug )

        # Convert to Cartesian coordinates
        Fx = cos*Fr - sin*Ft
        Fy = sin*Fr + cos*Ft

        # Obtain the a field at time n+1/2
        dtF = 0.5 * dt * dtF + F

        # Convert to grad_a^2 and a^2
        Fx = 2 * (Fx * F.conjugate() ).real
        Fy = 2 * (Fy * F.conjugate() ).real
        Fz = 2 * (Fz * F.conjugate() ).real
        F = F * F.conjugate()
        dtF = dtF * dtF.conjugate()

        # Register in the particle arrays
        if averaging:
            a2[i] = (0.5 * (a2[i] + F)).real
            grad_a2_x[i] = (0.5 * (grad_a2_x[i] + Fx)).real
            grad_a2_y[i] = (0.5 * (grad_a2_y[i] + Fy)).real
            grad_a2_z[i] = (0.5 * (grad_a2_z[i] + Fz)).real
            a2_delayed[i] = (0.5 * (a2_delayed[i] + F)).real
        else:
            a2[i] = F.real
            grad_a2_x[i] = Fx.real
            grad_a2_y[i] = Fy.real
            grad_a2_z[i] = Fz.real
            a2_delayed[i] = dtF.real


# -----------------------
# Field gathering cubic
# -----------------------

@njit_parallel
def gather_field_numba_cubic(x, y, z,
                    invdz, zmin, Nz,
                    invdr, rmin, Nr,
                    Er_m0, Et_m0, Ez_m0,
                    Er_m1, Et_m1, Ez_m1,
                    Br_m0, Bt_m0, Bz_m0,
                    Br_m1, Bt_m1, Bz_m1,
                    Ex, Ey, Ez,
                    Bx, By, Bz,
                    nthreads, ptcl_chunk_indices):
    """
    Gathering of the fields (E and B) using numba with multi-threading.
    Iterates over the particles, calculates the weighted amount
    of fields acting on each particle based on its shape (cubic).
    Fields are gathered in cylindrical coordinates and then
    transformed to cartesian coordinates.
    Supports only mode 0 and 1.

    Parameters
    ----------
    x, y, z : 1darray of floats (in meters)
        The position of the particles

    invdz, invdr : float (in meters^-1)
        Inverse of the grid step along the considered direction

    zmin, rmin : float (in meters)
        Position of the edge of the simulation box along the
        direction considered

    Nz, Nr : int
        Number of gridpoints along the considered direction

    Er_m0, Et_m0, Ez_m0 : 2darray of complexs
        The electric fields on the interpolation grid for the mode 0

    Er_m1, Et_m1, Ez_m1 : 2darray of complexs
        The electric fields on the interpolation grid for the mode 1

    Br_m0, Bt_m0, Bz_m0 : 2darray of complexs
        The magnetic fields on the interpolation grid for the mode 0

    Br_m1, Bt_m1, Bz_m1 : 2darray of complexs
        The magnetic fields on the interpolation grid for the mode 1

    Ex, Ey, Ez : 1darray of floats
        The electric fields acting on the particles
        (is modified by this function)

    Bx, By, Bz : 1darray of floats
        The magnetic fields acting on the particles
        (is modified by this function)

    nthreads : int
        Number of CPU threads used with numba prange

    ptcl_chunk_indices : array of int, of size nthreads+1
        The indices (of the particle array) between which each thread
        should loop. (i.e. divisions of particle array between threads)
    """
    # Gather the field per cell in parallel
    for nt in prange( nthreads ):

        # Create private arrays for each thread
        # to store the particle index and shape
        Sr = np.empty( 4 )
        Sz = np.empty( 4 )

        # Loop over all particles in thread chunk
        for i in range( ptcl_chunk_indices[nt],
                            ptcl_chunk_indices[nt+1] ):

            # Preliminary arrays for the cylindrical conversion
            # --------------------------------------------
            # Position
            xj = x[i]
            yj = y[i]
            zj = z[i]

            # Cylindrical conversion
            rj = math.sqrt(xj**2 + yj**2)
            if (rj != 0.):
                invr = 1./rj
                cos = xj*invr  # Cosine
                sin = yj*invr  # Sine
            else:
                cos = 1.
                sin = 0.
            exptheta_m0 = 1.
            exptheta_m1 = cos - 1.j*sin

            # Get weights for the deposition
            # --------------------------------------------
            # Positions of the particle, in the cell unit
            r_cell = invdr*(rj - rmin) - 0.5
            z_cell = invdz*(zj - zmin) - 0.5

            # Calculate the shape factors
            ir_lowest = int64(math.floor(r_cell)) - 1
            r_local = r_cell-ir_lowest
            Sr[0] = -1./6. * (r_local-2.)**3
            Sr[1] = 1./6. * (3.*(r_local-1.)**3 - 6.*(r_local-1.)**2 + 4.)
            Sr[2] = 1./6. * (3.*(2.-r_local)**3 - 6.*(2.-r_local)**2 + 4.)
            Sr[3] = -1./6. * (1.-r_local)**3
            iz_lowest = int64(math.floor(z_cell)) - 1
            z_local = z_cell-iz_lowest
            Sz[0] = -1./6. * (z_local-2.)**3
            Sz[1] = 1./6. * (3.*(z_local-1.)**3 - 6.*(z_local-1.)**2 + 4.)
            Sz[2] = 1./6. * (3.*(2.-z_local)**3 - 6.*(2.-z_local)**2 + 4.)
            Sz[3] = -1./6. * (1.-z_local)**3

            # E-Field
            # -------
            Fr = 0.
            Ft = 0.
            Fz = 0.
            # Add contribution from mode 0
            Fr, Ft, Fz = add_cubic_gather_for_mode( 0,
                Fr, Ft, Fz, exptheta_m0, Er_m0, Et_m0, Ez_m0,
                ir_lowest, iz_lowest, Sr, Sz, Nr, Nz )
            # Add contribution from mode 1
            Fr, Ft, Fz = add_cubic_gather_for_mode( 1,
                Fr, Ft, Fz, exptheta_m1, Er_m1, Et_m1, Ez_m1,
                ir_lowest, iz_lowest, Sr, Sz, Nr, Nz )
            # Convert to Cartesian coordinates
            # and write to particle field arrays
            Ex[i] = cos*Fr - sin*Ft
            Ey[i] = sin*Fr + cos*Ft
            Ez[i] = Fz

            # B-Field
            # -------
            # Clear the placeholders for the
            # gathered field for each coordinate
            Fr = 0.
            Ft = 0.
            Fz = 0.
            # Add contribution from mode 0
            Fr, Ft, Fz =  add_cubic_gather_for_mode( 0,
                Fr, Ft, Fz, exptheta_m0, Br_m0, Bt_m0, Bz_m0,
                ir_lowest, iz_lowest, Sr, Sz, Nr, Nz )
            # Add contribution from mode 1
            Fr, Ft, Fz =  add_cubic_gather_for_mode( 1,
                Fr, Ft, Fz, exptheta_m1, Br_m1, Bt_m1, Bz_m1,
                ir_lowest, iz_lowest, Sr, Sz, Nr, Nz )
            # Convert to Cartesian coordinates
            # and write to particle field arrays
            Bx[i] = cos*Fr - sin*Ft
            By[i] = sin*Fr + cos*Ft
            Bz[i] = Fz

    return Ex, Ey, Ez, Bx, By, Bz


@numba.njit
def gather_envelope_field_numba_cubic(x, y, z,
                    invdz, zmin, Nz,
                    invdr, rmin, Nr, dt,
                    a_tuple, grad_a_r_tuple, grad_a_t_tuple, grad_a_z_tuple,
                    dta_tuple, m_tuple,
                    a2, grad_a2_x, grad_a2_y, grad_a2_z, a2_delayed,
                    nthreads, ptcl_chunk_indices, averaging = False):
    """
    Gathering of the envelope fields a2 and grad_a2 using numba
    with multi-threading.
    Iterates over the particles, calculates the weighted amount
    of fields acting on each particle based on its shape (cubic).
    Fields are gathered in cylindrical coordinates and then
    transformed to cartesian coordinates.

    Parameters
    ----------
    x, y, z : 1darray of floats (in meters)
        The position of the particles

    invdz, invdr : float (in meters^-1)
        Inverse of the grid step along the considered direction

    zmin, rmin : float (in meters)
        Position of the edge of the simulation box along the
        direction considered

    Nz, Nr : int
        Number of gridpoints along the considered direction

    a_tuple, grad_a_r_tuple, grad_a_t_tuple, grad_a_z_tuple :
        tuple of 2darray of complexs
        The relevant fields on the interpolation grid for all the different modes

    m: tuple
        Indices of the azimuthal mode

    a, grad_a_x, grad_a_y, grad_a_z : 1darray of floats
        The relevant fields acting on the particles
        (is modified by this function)

    averaging : boolean, optional
        Whether to average the new values with the old ones or to
        discard the old values.
    """
    # Gather the field per cell in parallel
    for nt in prange( nthreads ):

        # Create private arrays for each thread
        # to store the particle index and shape
        Sr = np.empty( 4 )
        Sz = np.empty( 4 )

        # Loop over all particles in thread chunk
        for i in range( ptcl_chunk_indices[nt],
                            ptcl_chunk_indices[nt+1] ):

            # Preliminary arrays for the cylindrical conversion
            # --------------------------------------------
            # Position
            xj = x[i]
            yj = y[i]
            zj = z[i]

            # Cylindrical conversion
            rj = math.sqrt(xj**2 + yj**2)
            if (rj != 0.):
                invr = 1./rj
                cos = xj*invr  # Cosine
                sin = yj*invr  # Sine
            else:
                cos = 1.
                sin = 0.

            # Get weights for the deposition
            # --------------------------------------------
            # Positions of the particle, in the cell unit
            r_cell = invdr*(rj - rmin) - 0.5
            z_cell = invdz*(zj - zmin) - 0.5

            # Calculate the shape factors
            ir_lowest = int64(math.floor(r_cell)) - 1
            r_local = r_cell-ir_lowest
            Sr[0] = -1./6. * (r_local-2.)**3
            Sr[1] = 1./6. * (3.*(r_local-1.)**3 - 6.*(r_local-1.)**2 + 4.)
            Sr[2] = 1./6. * (3.*(2.-r_local)**3 - 6.*(2.-r_local)**2 + 4.)
            Sr[3] = -1./6. * (1.-r_local)**3
            iz_lowest = int64(math.floor(z_cell)) - 1
            z_local = z_cell-iz_lowest
            Sz[0] = -1./6. * (z_local-2.)**3
            Sz[1] = 1./6. * (3.*(z_local-1.)**3 - 6.*(z_local-1.)**2 + 4.)
            Sz[2] = 1./6. * (3.*(2.-z_local)**3 - 6.*(2.-z_local)**2 + 4.)
            Sz[3] = -1./6. * (1.-z_local)**3

            # Envelope fields
            # -------
            F = 0.
            Fr = 0.
            Ft = 0.
            Fz = 0.
            dtF = 0.
            for m in m_tuple:
                # Add contribution from mode m
                a_m = a_tuple[m]
                grad_a_r_m = grad_a_r_tuple[m]
                grad_a_t_m = grad_a_t_tuple[m]
                grad_a_z_m = grad_a_z_tuple[m]
                dta_m = dta_tuple[m]
                exptheta_m = (cos - 1.j*sin)**m
                F, Fr, Ft, Fz, dtF = add_cubic_envelope_gather_for_mode( m, F,
                            Fr, Ft, Fz, dtF, exptheta_m, a_m, grad_a_r_m,
                            grad_a_t_m, grad_a_z_m, dta_m,
                            ir_lowest, iz_lowest, Sr, Sz, Nr, Nz  )

            # Convert to Cartesian coordinates
            Fx = cos*Fr - sin*Ft
            Fy = sin*Fr + cos*Ft

            # Obtain the a field at time n+1/2
            dtF = 0.5 * dt * dtF + F

            # Convert to grad_a^2 and a^2
            Fx = 2 * (Fx * F.conjugate() ).real
            Fy = 2 * (Fy * F.conjugate() ).real
            Fz = 2 * (Fz * F.conjugate() ).real
            F = F * F.conjugate()
            dtF = dtF * dtF.conjugate()

            # Register in the particle arrays
            if averaging:
                a2[i] = (0.5 * (a2[i] + F)).real
                grad_a2_x[i] = (0.5 * (grad_a2_x[i] + Fx)).real
                grad_a2_y[i] = (0.5 * (grad_a2_y[i] + Fy)).real
                grad_a2_z[i] = (0.5 * (grad_a2_z[i] + Fz)).real
                a2_delayed[i] = (0.5 * (a2_delayed[i] + F)).real
            else:
                a2[i] = F.real
                grad_a2_x[i] = Fx.real
                grad_a2_y[i] = Fy.real
                grad_a2_z[i] = Fz.real
                a2_delayed[i] = dtF.real
