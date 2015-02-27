"""
Discrete Hankel Transform, with several numerical methods available.

Definition of the Hankel forward and backward transform of order p :
g(\nu) = 2 \pi \int_0^\infty f(r) J_p( 2 \pi \nu r) r dr
f( r ) = 2 \pi \int_0^\infty g(\nu) J_p( 2 \pi \nu r) \nu d\nu

Several method exist to discretize this transform, with usually non-uniform
discretization grids in r and \nu.

Available methods :
-------------------

- FHT (Fast Hankel Transform) :
  In theory, calculates the transform in N log(N) time, but is not appropriate
  for successions of forward transformation and backward transformation
  (accuracy issues).
  The discretization r grid is exponentially spaced, with considerable
  oversampling close to the axis.

- QDHT (Quasi-Discrete Hankel Transform) :
  Calculates the transform in N^2 time. Ensures that the succession
  of a forward and backward transformation retrieves the original function
  (with a very good accuracy).
  The discretization r grid corresponds to the zeros of the Bessel function
  of order p. 
  
See the docstring of the DHT object for usage instructions.
"""

import numpy as np
from scipy.special import jn, jn_zeros
from scipy.interpolate import interp1d
from scipy.optimize import fsolve
from utils import array_multiply

# The list of available methods
available_methods = [ # 'FHT',
                      'QDHT', 'MDHT(m+1,m)', 'MDHT(m-1,m)', 'MDHT(m,m)']

class DHT(object) :
    """
    Class that allows to perform the Discrete Hankel Transform.
        
    Usage : (for a callable f for instance)
    >>> trans = DHT(0,10,1,'QDHT')
    >>> r = trans.get_r()  # Array of radial position
    >>> F = f(r)           # Calculate the values of the function
                           # At these positions
    >>> G = trans.transform(F)
    """

    def __init__(self, p, N, rmax, method, **kw ) :
        """
        Calculate the r (position) and nu (frequency) grid
        on which the transform will operate.

        Also store auxiliary data needed for the transform.
        
        Parameters :
        ------------
        p : int
        Order of the Hankel transform

        N : float
        Number of points of the r grid

        rmax : float
        Maximal radius of the r grid.
        (The function is assumed to be zero at that point.)

        method : string
        The method used to calculate the Hankel transform
        
        kw : optional arguments to be passed in the case of the MDHT
        """
        
        # Check that the method is valid
        if ( method in available_methods ) == False :
            raise ValueError('Illegal method string')
        else :
            self.method = method

        # Call the corresponding initialization routine
        if self.method == 'FHT' :
            self.FHT_init(p, N, rmax)
        elif self.method == 'QDHT' :
            self.QDHT_init(p, N, rmax)
        elif self.method == 'MDHT(m,m)' :
            self.MDHT_init(p, N, rmax, m=p, **kw)
        elif self.method == 'MDHT(m-1,m)' :
            self.MDHT_init(p, N, rmax, m=p+1, **kw)
        elif self.method == 'MDHT(m+1,m)' :
            self.MDHT_init(p, N, rmax, m=p-1, **kw)

        
    def get_r(self) :
        """
        Return the natural, non-uniform r grid for the chosen method

        Returns :
        ---------
        A real 1darray containing the values of the positions
        """
        return( self.r )

        
    def get_nu(self) :
        """
        Return the natural, non-uniform nu grid for the chosen method

        Returns :
        ---------
        A real 1darray containing the values of the frequencies
        """
        return( self.nu )
            
            
    def transform( self, f, axis=-1, r=None, nu=None) :
        """
        Perform the Hankel transform of f, according to the method
        chosen at initialization.

        Parameters :
        ------------
        f : ndarray of real or complex values
        Array containing the discrete values of the function for which
        the discrete Hankel transform is to be calculated.

        axis : int, optional
        The axis of the array f along which the Hankel transform is performed.
        If axis not given, the last axis is used.

        r : 1darray, optional
        The r grid on which f has been sampled
        If r is not given, it is assumed that f has been sampled on the
        natural grid for this transform, i.e. self.r.

        nu : 1darray, optional
        The nu grid on which the Hankel transform is to be evaluated.
        If nu is not given, it is assumed that the transform should be
        evaluated on the natural grid, i.e. self.nu.

        Returns :
        ---------
        A ndarray of the same shape as f, containing the value of the transform
        """
        
        # Interpolate f from r to self.r, if needed
        if r is not None :
            f_interp = interp1d( r, f, axis=axis,
                          copy=False, assume_sorted=True, bounds_error=False )
            F = f_interp( self.r )
        else :
            assert ( f.shape[axis] == self.N) , \
            'The axis %d of f should have the same length as self.r.' %axis
            F = f
           
        # Perform the transform
        if self.method == 'FHT' :
            G = self.FHT_transform(F, axis)
        elif self.method == 'QDHT' :
            G = self.QDHT_transform(F, axis)
        elif self.method in [ 'MDHT(m,m)', 'MDHT(m-1,m)', 'MDHT(m+1,m)' ] :
            G = self.MDHT_transform(F, axis)
        
        # Interpolate back G from self.nu to nu, if needed
        if nu is not None :
            G_interp = interp1d( self.nu, G, axis=axis,
                          copy=False, assume_sorted=True, bounds_error=False )
            g = G_interp( nu )
        else :
            g = G

        return( g )
        

    def inverse_transform( self, g, axis=-1, nu=None, r=None) :
        """
        Perform the Hankel inverse transform of g, according to the method
        chosen at initialization.

        Parameters :
        ------------
        g : ndarray of real or complex values
        Array containing the values of the function for which
        the discrete inverse Hankel transform is to be calculated.

        axis : int, optional
        The axis of the array f along which the inverse transform is performed.
        If axis not given, the last axis is used.

        nu: 1darray, optional
        The nu grid on which g has been sampled
        If nu is not given, it is assumed that g has been sampled on the
        natural grid for this transform, i.e. self.nu.

        r : 1darray, optional
        The r grid on which the Hankel inverse transform is to be evaluated.
        If r is not given, it is assumed that the transform should be
        evaluated on the natural grid, i.e. self.r.

        Returns :
        ---------
        A ndarray of the same shape as g, containing the value of the inverse
        transform
        """
        
        # Interpolate g from nu to self.nu if needed
        if nu is not None :
            g_interp = interp1d( nu, g, axis=axis,
                          copy=False, assume_sorted=True, bounds_error=False )
            G = g_interp( self.nu )
        else :
            assert ( g.shape[axis] == self.N), \
              'The axis %d of g should have the same length as self.nu.' %axis
            G = g
           
        # Perform the transform
        if self.method == 'FHT' :
            F = self.FHT_inverse_transform( G, axis)
        elif self.method == 'QDHT' :
            F = self.QDHT_inverse_transform( G, axis)
        elif self.method in [ 'MDHT(m,m)', 'MDHT(m-1,m)', 'MDHT(m+1,m)' ] :
            F = self.MDHT_inverse_transform( G, axis)
        
        # Interpolate F from self.r to r if needed
        if nu is not None :
            F_interp = interp1d( self.r, G, axis=axis,
                          copy=False, assume_sorted=True, bounds_error=False )
            f = F_interp( r )
        else :
            f = F

        return(f)


    def MDHT_init(self, p, N, rmax, m, d=None, Fw='symmetric') :
        """
        Calculate r and nu for the MDHT.
        Custom Hankel Transform, see the paper associated with FBPIC

        Grid :
        r_n = n*rmax/N
        nu_n = alpha_{m,n}
        where alpha_{m,n} is the n^th zero of the m^th Bessel function
        
        m : int
           Index of the nu grid on which to evaluate the Hankel
           transform. This can only be p-1, p or p+1 for the
           algorithm to work.

        d : float, optional
           Offset of the regularly-spaced radial grid, within one cell
           If None, this uses the zeros of the Bessel function.
           (nu_n = alpha_n/(2*pi*rmax), r_n = alpha_n*rmax/S

        Fw : string, optional
           Method to calculate the forward transformation
           If 'symmetric', uses a symmetric formula for the inverse matrix
           If 'inverse', inverses the forward matrix to find the inverse matrix
        
        Also store the auxilary matrices M and invM.
        """
        # Check that m has a valid value
        if (m in [p-1, p, p+1]) == False :
            raise ValueError(
                'm must be either %d, %d or %d, but is %d'  %(p-1,p,p+1,m))
        
        # Register values
        self.d = d
        self.Fw =Fw
        self.p = p
        self.m = m
        
        # Calculate the zeros of the Bessel function
        if m == 0 : # 0 is not a zero of the Bessel function
            zeros = jn_zeros(m, N+1)
        else : # 0 is a zero of the Bessel function
            zeros = np.hstack( (np.array([0.]), jn_zeros(m, N)) )
        last_alpha = zeros[-1] # The N+1^{th} zero
        alphas = zeros[:-1]    # The N first zeros

        # Calculate the grid
        self.N = N
        self.rmax = rmax
        self.nu = ( 1./(2*np.pi*rmax) ) * alphas
        if d is not None :
            print ('Using uniform grid')
            self.r = (rmax*1./N) * ( np.arange(N) + d )
        else :
            if m != p :
                print('')
                print('Using special formula')
                k = int(N/4) 
                A = alphas[k]
                J = jn_zeros(m,N)[-1]
                S = abs(2./jn( m-1, alphas[k]))*np.sqrt(
                1 + ( jn( m-1, A*alphas[1:]/J )**2 / \
                    jn( m-1, alphas[1:] )**2 ).sum() 
                )
                print('S = %f' %S)
                print('Instead of S = %f' %last_alpha )
            else :
                S = last_alpha
            self.r = rmax*alphas/S

        # Calculate and store the inverse matrix invM
        # (imposed by the condition that the modes give delta functions)
        if p == m :
            denom = 1./( np.pi * rmax**2 * jn(m+1,alphas)**2 )
        else :
            denom = 1./( np.pi * rmax**2 * jn(p, alphas)**2 )
        num = jn( p, 2*np.pi* self.r[:, np.newaxis]*self.nu[np.newaxis,:] )
        self.invM = num * denom[np.newaxis, :]

        # Calculate the matrix M
        if Fw == 'inverse' :
            self.M = np.linalg.inv( self.invM )
        if Fw == 'symmetric' :
            num = jn( p, 2*np.pi* self.nu[:, np.newaxis]*self.r[np.newaxis,:] )
            self.M = (2*np.pi*rmax**2/S)**2 * num * denom[ np.newaxis, :]


    def MDHT_transform( self, F, axis ) :
        """
        Performs the MDHT of F and returns the results.
        Reference: see the paper associated with FBPIC

        F : ndarray of real or complex values
        Array containing the values from which to compute the DHT.

        axis : int
        The axis of the array F along which the DHT is performed.
        """

        # Perform the matrix product with M
        G = np.tensordot( F, self.M, axes = (axis,-1) )

        # By default, the axis of the transform becomes the last
        # axis after tensordot. Change this if needed.
        if axis != -1 :
            G = G.swapaxes(-1, axis)

        return( G )

        
    def MDHT_inverse_transform( self, G, axis ) :
        """
        Performs the MDHT of G and returns the results.
        Reference: see the paper associated with FBPIC

        G : ndarray of real or complex values
        Array containing the values from which to compute the DHT.

        axis : int
        The axis of the array F along which the DHT is performed.
        """

        # Perform the matrix product with invM
        F = np.tensordot( G, self.invM, axes = (axis,-1) )
        
        # By default, the axis of the transform becomes the last
        # axis after tensordot. Change this if needed.
        if axis != -1 :
            F = F.swapaxes(-1, axis)

        return( F )

        
    def QDHT_init(self,p,N,rmax) :
        """
        Calculate r and nu for the QDHT.
        Reference : Guizar-Sicairos et al., J. Opt. Soc. Am. A 21 (2004)

        Also store the auxilary matrix T and vectors J and J_inv required for
        the transform.

        Grid : r_n = alpha_{p,n}*rmax/alpha_{p,N+1}
        where alpha_{p,n} is the n^th zero of the p^th Bessel function
        """

        # Calculate the zeros of the Bessel function
        zeros = jn_zeros(p,N+1)
                
        # Calculate the grid
        last_alpha = zeros[-1] # The N+1^{th} zero
        alphas = zeros[:-1]    # The N first zeros
        numax = last_alpha/(2*np.pi*rmax) 
        self.N = N
        self.rmax = rmax
        self.numax = numax
        self.r = rmax*alphas/last_alpha 
        self.nu = numax*alphas/last_alpha

        # Calculate and store the vector J
        J = abs( jn(p+1,alphas) )
        self.J = J
        self.J_inv = 1./J

        # Calculate and store the matrix T
        denom = J[:,np.newaxis]*J[np.newaxis,:]*last_alpha
        num = 2*jn( p, alphas[:,np.newaxis]*alphas[np.newaxis,:]/last_alpha )
        self.T = num/denom
        
    def QDHT_transform( self, F, axis ) :
        """
        Performs the QDHT of F and returns the results.
        Reference : Guizar-Sicairos et al., J. Opt. Soc. Am. A 21 (2004)

        F : ndarray of real or complex values
        Array containing the values from which to compute the FHT.

        axis : int
        The axis of the array F along which the FHT is performed.
        """

        # Multiply the input function by the vector J_inv
        F = array_multiply( F, self.J_inv*self.rmax, axis )

        # Perform the matrix product with T
        G = np.tensordot( F, self.T, axes = (axis,-1) )

        # By default, the axis of the transform becomes the last
        # axis after tensordot. Change this if needed.
        if axis != -1 :
            G = G.swapaxes(-1, axis)

        # Multiply the result by the vector J
        G = array_multiply( G, self.J / self.numax, axis )

        return( G )

    def QDHT_inverse_transform( self, G, axis ) :
        """
        Performs the QDHT of G and returns the results.
        Reference : Guizar-Sicairos et al., J. Opt. Soc. Am. A 21 (2004)

        G : ndarray of real or complex values
        Array containing the values from which to compute the DHT.

        axis : int
        The axis of the array F along which the DHT is performed.
        """

        # Multiply the input function by the vector J_inv
        G =  array_multiply( G, self.J_inv*self.numax, axis ) 

        # Perform the matrix product with T
        F = np.tensordot( G, self.T, axes = (axis,-1) )
        
        # By default, the axis of the transform becomes the last
        # axis after tensordot. Change this if needed.
        if axis != -1 :
            F = F.swapaxes(-1, axis)

        # Multiply the result by the vector J
        F = array_multiply( F, self.J / self.rmax, axis )

        return( F )
        
    def FHT_init(self,p,N,rmax) :
        """
        Calculate r and nu for the FHT.
        Reference : A. Siegman, Optics Letters 1 (1977) 

        Also store the auxilary vector fft_j_convol needed for the
        transformation.
        
        Grid : r = dr*exp( alpha*n )
          with rmax = dr*exp( alpha*N )
          and exp( alpha*N )*(1-exp(-alpha)) 
         """

        # Minimal number of points of the r grid, within one
        # oscillation of the highest frequency of the nu grid
        # (Corresponds to K1 and K2, in Siegman's article, with
        # K1 = K2 = K here.)   
        K = 4.
        
        # Find the alpha corresponding to N
        alpha = fsolve( lambda x : np.exp(x*N)*(1-np.exp(-x)) - 1,
                        x0 = 1. )[0]
        # Corresponding dr
        dr = rmax/np.exp( alpha*N )
        # The r and nu grid.
        self.N = N
        self.r = dr*np.exp( alpha*np.arange(N) )
        self.nu = 1./(K*rmax)*np.exp( alpha*np.arange(N) )

        # Store vector containing the convolutional filter
        r_nu = dr/(K*rmax) * np.exp( alpha*np.arange(2*N) )
        j_convol = 2*np.pi* alpha * r_nu * jn( p, 2*np.pi * r_nu )
        self.fft_j_convol = np.fft.ifft( j_convol )

        
    def FHT_transform( self, F, axis ) :
        """
        Performs the FHT of F and returns the results.
        Reference : A. Siegman, Optics Letters 1 (1977)

        F : ndarray of real or complex values
        Array containing the values from which to compute the FHT.

        axis : int
        The axis of the array F along which the FHT is performed.
        """
        # This function calculates the convolution of j_convol and F
        # by multiplying their fourier transform
        
        # Multiply F by self.r, along axis
        rF = array_multiply( F, self.r, axis )
        # Perform the FFT of rF with 0 padding from N to 2N along axis
        fft_rF = np.fft.fft( rF, axis=axis, n=2*self.N )

        # Mutliply fft_rF and fft_j_convol, along axis
        fft_nuG = array_multiply( fft_rF, self.fft_j_convol, axis )

        # Perform the FFT again
        nuG_large = np.fft.fft( fft_nuG, axis=axis )
        # Discard the N last values along axis, and divide by nu
        nuG = np.split( nuG_large, 2, axis=axis )[0]
        G  = array_multiply( nuG, 1./self.nu, axis )

        return( G )
        
    def FHT_inverse_transform( self, G, axis ) :
        """
        Performs the inverse FHT of G and returns the results.
        Reference : A. Siegman, Optics Letters 1 (1977)

        G : ndarray of real or complex values
        Array containing the values from which to compute the inverse FHT.

        axis : int
        The axis of the array G along which the inverse FHT is performed.
        """
        # This function calculates the convolution of j_convol and G
        # by multiplying their fourier transform
        
        # Multiply G by self.nu, along axis
        nuG = array_multiply( G, self.nu, axis )
        # Perform the FFT of nuG with 0 padding from N to 2N along axis
        fft_nuG = np.fft.fft( nuG, axis=axis, n=2*self.N )

        # Mutliply fft_nuG and fft_j_convol, along axis
        fft_rF = array_multiply( fft_nuG, self.fft_j_convol, axis )

        # Perform the FFT again
        rF_large = np.fft.fft( fft_rF, axis=axis )
        # Discard the N last values along axis, and divide by r
        rF = np.split( rF_large, 2, axis=axis )[0]
        F  = array_multiply( rF, 1./self.r, axis )

        return( F )

