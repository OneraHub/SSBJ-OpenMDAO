"""
SSBJ test case - http://ntrs.nasa.gov/archive/nasa/casi.ntrs.nasa.gov/19980234657.pdf
Python implementation and OpenMDAO integration developed by
Sylvain Dubreuil and Remi Lafage of ONERA, the French Aerospace Lab.
"""
from __future__ import print_function
import numpy as np
from openmdao.api import ExplicitComponent
from .common import PolynomialFunction, WFO, WO, NZ
# pylint: disable=C0103

def structure(pf, x_str, Z, L, WE):
    t = Z[0]*Z[5]/(np.sqrt(abs(Z[5]*Z[3])))
    b = np.sqrt(abs(Z[5]*Z[3]))/2.0
    R = (1.0+2.0*x_str[0])/(3.0*(1.0+x_str[0]))
    Theta = pf([abs(x_str[1]), b, R, L],
                         [2, 4, 4, 3], [0.25]*4, "twist")

    Fo1 = pf([x_str[1]], [1], [.008], "Fo1")

    WT_hat = L
    WW = Fo1 * (0.0051 * abs(WT_hat*NZ)**0.557 * \
                abs(Z[5])**0.649 * abs(Z[3])**0.5 * abs(Z[0])**(-0.4) \
                * abs(1.0+x_str[0])**0.1 * (0.1875*abs(Z[5]))**0.1 \
                / abs(np.cos(Z[4]*np.pi/180.)))
    WFW = 5.0/18.0 * abs(Z[5]) * 2.0/3.0 * t * 42.5
    WF = WFW + WFO
    WT = WO + WW + WF + WE
    sigma = 5*[0.]
    sigma[0] = pf([Z[0], L, x_str[1], b, R], [4, 1, 4, 1, 1], [0.1]*5, "sigma[1]")
    sigma[1] = pf([Z[0], L, x_str[1], b, R], [4, 1, 4, 1, 1], [0.15]*5, "sigma[2]")
    sigma[2] = pf([Z[0], L, x_str[1], b, R], [4, 1, 4, 1, 1], [0.2]*5, "sigma[3]")
    sigma[3] = pf([Z[0], L, x_str[1], b, R], [4, 1, 4, 1, 1], [0.25]*5, "sigma[4]")
    sigma[4] = pf([Z[0], L, x_str[1], b, R], [4, 1, 4, 1, 1], [0.30]*5, "sigma[5]")
    return Theta, WF, WT, sigma

class Structure(ExplicitComponent):

    def __init__(self, scalers):
        super(Structure, self).__init__()
        # scalers values
        self.scalers = scalers
        # Polynomial function initialized with given constant values
        self.pf = PolynomialFunction()

    def setup(self):
        # Global Design Variable z=(t/c,h,M,AR,Lambda,Sref)
        self.add_input('z', val=np.zeros(6))
        # Local Design Variable x_str=(lambda,section caisson)
        self.add_input('x_str', val=np.zeros(2))
        # Coupling parameters
        self.add_input('L', val=1.0)
        self.add_input('WE', val=1.0)
        # Coupling output
        self.add_output('WT', val=1.0)
        self.add_output('Theta', val=1.0)
        self.add_output('WF', val=1.0)
        self.add_output('sigma', val=np.zeros(5))
        self.declare_partials('*', '*')

    def compute(self, inputs, outputs):
        Z = inputs['z']*self.scalers['z']
        x_str = inputs['x_str']*self.scalers['x_str']
        L = inputs['L']*self.scalers['L']
        WE = inputs['WE']*self.scalers['WE']

        Theta, WF, WT, sigma = structure(self.pf, x_str, Z, L, WE)

        #Unknowns
        outputs['Theta'] = Theta/self.scalers['Theta']
        outputs['WF'] = WF/self.scalers['WF']
        outputs['WT'] = WT/self.scalers['L']
        outputs['sigma'] = np.zeros(5)
        for i in range(5):
            outputs['sigma'][i] = sigma[i]/self.scalers['sigma'][i]

    def compute_partials(self, inputs, J):

        Z = inputs['z']*self.scalers['z']
        Xstr = inputs['x_str']*self.scalers['x_str']
        L = inputs['L']*self.scalers['L']

        # dWT ################################################################
        Fo1 = self.pf([Xstr[1]], [1], [.008], "Fo1")

        dWtdlambda = 0.1*Fo1/np.cos(Z[4]*np.pi/180.)*0.0051 \
            *(abs(L)*NZ)**0.557*abs(Z[5])**0.649 \
            * abs(Z[3])**0.5 * abs(Z[0])**(-0.4) \
            * (1.0+Xstr[0])**-0.9 * (0.1875*abs(Z[5]))**0.1
        A = (0.0051 * abs(L*NZ)**0.557 * abs(Z[5])**0.649 \
             * abs(Z[3])**0.5 * abs(Z[0])**(-0.4) * abs(1.0+Xstr[0])**0.1 \
             * (0.1875*abs(Z[5]))**0.1 / abs(np.cos(Z[4]*np.pi/180.)))

        S_shifted, Ai, Aij = self.pf([Xstr[1]], [1], [.008],
                                          "Fo1", deriv=True)
        if Xstr[1]/self.pf.d['Fo1'][0]>=0.75 and Xstr[1]/self.pf.d['Fo1'][0]<=1.25:
            dSxdx = 1.0/self.pf.d['Fo1'][0]
        else:
            dSxdx = 0.0

        dWtdx = A*(Ai[0]*dSxdx \
                   + Aij[0, 0]*dSxdx*S_shifted[0, 0])

        val = np.append(dWtdlambda/self.scalers['L'], dWtdx/self.scalers['L'])
        J['WT', 'x_str'] = np.array([val])*self.scalers['x_str']
        dWTdtc = -0.4*Fo1/np.cos(Z[4]*np.pi/180.)*0.0051 \
            * abs(L*NZ)**0.557 * abs(Z[5])**0.649 \
            * abs(Z[3])**0.5*abs(Z[0])**(-1.4)*abs(1.0+Xstr[0])**0.1 \
            * (0.1875*abs(Z[5]))**0.1  +  212.5/27.*Z[5]**(3.0/2.0)/np.sqrt(Z[3])
        dWTdh = 0.0
        dWTdM = 0.0
        dWTdAR = 0.5*Fo1/np.cos(Z[4]*np.pi/180.)* 0.0051 \
            * abs(L*NZ)**0.557 * abs(Z[5])**0.649 \
            * abs(Z[3])**-0.5*abs(Z[0])**(-0.4)*abs(1.0+Xstr[0])**0.1 \
            * (0.1875*abs(Z[5]))**0.1 + 212.5/27.*Z[5]**(3.0/2.0) \
            * Z[0] * -0.5*Z[3]**(-3.0/2.0)
        dWTdLambda = Fo1*np.pi/180.*np.sin(Z[4]*np.pi/180.)/np.cos(Z[4]*np.pi/180.)**2 \
            * 0.0051 * abs(L*NZ)**0.557 * abs(Z[5])**0.649 \
            * abs(Z[3])**0.5*abs(Z[0])**(-0.4)*abs(1.0+Xstr[0])**0.1 \
            * (0.1875*abs(Z[5]))**0.1
        dWTdSref = 0.749*Fo1/np.cos(Z[4]*np.pi/180.)*0.1875**(0.1)*0.0051 \
            * abs(L*NZ)**0.557*abs(Z[5])**-0.251 \
            *abs(Z[3])**0.5*abs(Z[0])**(-0.4)*abs(1.0+Xstr[0])**0.1 \
            + 637.5/54.*Z[5]**(0.5)*Z[0]/np.sqrt(Z[3])
        val = np.append(dWTdtc/self.scalers['L'],
                                  [dWTdh/self.scalers['L'],
                                  dWTdM/self.scalers['L'],
                                  dWTdAR/self.scalers['L'],
                                  dWTdLambda/self.scalers['L'],
                                  dWTdSref/self.scalers['L']])
        J['WT', 'z'] = np.array([val])*self.scalers['z']               
        dWTdL = 0.557*Fo1/np.cos(Z[4]*np.pi/180.)*0.0051 * abs(L)**-0.443 \
            *NZ**0.557* abs(Z[5])**0.649 * abs(Z[3])**0.5 \
            * abs(Z[0])**(-0.4) * abs(1.0+Xstr[0])**0.1 * (0.1875*abs(Z[5]))**0.1    
        J['WT', 'L'] = np.array([[dWTdL]])
        dWTdWE = 1.0
        J['WT', 'WE'] = np.array([[dWTdWE]])/self.scalers['L']*self.scalers['WE']

        # dWF ################################################################
        dWFdlambda = 0.0
        dWFdx = 0.0
        val = np.append(dWFdlambda/self.scalers['WF'], dWFdx/self.scalers['WF'])
        J['WF', 'x_str'] = np.array([val]) *self.scalers['x_str']
        dWFdtc = 212.5/27.*Z[5]**(3.0/2.0)/np.sqrt(Z[3])
        dWFdh = 0.0
        dWFdM = 0.0
        dWFdAR = 212.5/27.*Z[5]**(3.0/2.0) * Z[0] * -0.5*Z[3]**(-3.0/2.0)
        dWFdLambda = 0.0
        dWFdSref = 637.5/54.*Z[5]**(0.5)*Z[0]/np.sqrt(Z[3])
        val=np.append(dWFdtc/self.scalers['WF'],
                                  [dWFdh/self.scalers['WF'],
                                  dWFdM/self.scalers['WF'],
                                  dWFdAR/self.scalers['WF'],
                                  dWFdLambda/self.scalers['WF'],
                                  dWFdSref/self.scalers['WF']])
        J['WF', 'z'] = np.array([val])*self.scalers['z']
        dWFdL = 0.0
        J['WF', 'L'] = np.array([[dWFdL]])/self.scalers['WF']*self.scalers['L']
        dWFdWE = 0.0
        J['WF', 'WE'] = np.array([[dWFdWE]])/self.scalers['WF']*self.scalers['WE']

        ### dTheta ###########################################################
        b = np.sqrt(abs(Z[5]*Z[3]))/2.0
        R = (1.0+2.0*Xstr[0])/(3.0*(1.0+Xstr[0]))
        S_shifted, Ai, Aij = self.pf([abs(Xstr[1]), b, R, L],
                                          [2, 4, 4, 3],
                                          [0.25]*4, "twist", deriv=True)
        if R/self.pf.d['twist'][2]>=0.75 and R/self.pf.d['twist'][2]<=1.25:								  
            dSRdlambda = 1.0/self.pf.d['twist'][2]*1.0/(3.0*(1.0+Xstr[0])**2)
        else:
            dSRdlambda = 0.0

        dSRdlambda2 = 2.0*S_shifted[0, 2]*dSRdlambda
        dThetadlambda = Ai[2]*dSRdlambda + 0.5*Aij[2, 2]*dSRdlambda2 \
            + Aij[0, 2]*S_shifted[0, 0]*dSRdlambda \
            + Aij[1, 2]*S_shifted[0, 1]*dSRdlambda\
            + Aij[3, 2]*S_shifted[0, 3]*dSRdlambda
        if abs(Xstr[1])/self.pf.d['twist'][0]>=0.75 and abs(Xstr[1])/self.pf.d['twist'][0]<=1.25:	
            dSxdx = 1.0/self.pf.d['twist'][0]
        else:
            dSxdx = 0.0
        dSxdx2 = 2.0*S_shifted[0, 0]*dSxdx
        dThetadx = Ai[0]*dSxdx + 0.5*Aij[0, 0]*dSxdx2 \
            + Aij[1, 0]*S_shifted[0, 1]*dSxdx \
            + Aij[2, 0]*S_shifted[0, 2]*dSxdx \
            + Aij[3, 0]*S_shifted[0, 3]*dSxdx
        J['Theta', 'x_str'] = np.array([np.append(dThetadlambda[0, 0]/self.scalers['Theta'],
                                         dThetadx[0, 0]/self.scalers['Theta'])])\
            *self.scalers['x_str']
        dThetadtc = 0.0
        dThetadh = 0.0
        dThetadM = 0.0
        if b/self.pf.d['twist'][1]>=0.75 and b/self.pf.d['twist'][1]<=1.25:
            dSbdAR = 1.0/self.pf.d['twist'][1]*(np.sqrt(Z[5])/4.0*Z[3]**-0.5)
        else:
            dSbdAR = 0.0
        dSbdAR2 = 2.0*S_shifted[0, 1]*dSbdAR
        dThetadAR = Ai[1]*dSbdAR+0.5*Aij[1, 1]*dSbdAR2 \
            + Aij[0, 1]*S_shifted[0, 0]*dSbdAR \
            + Aij[2, 1]*S_shifted[0, 2]*dSbdAR \
            + Aij[3, 1]*S_shifted[0, 3]*dSbdAR
        dThetadLambda = 0.0
        if b/self.pf.d['twist'][1]>=0.75 and b/self.pf.d['twist'][1]<=1.25:
            dSbdSref= 1.0/self.pf.d['twist'][1]*(np.sqrt(Z[3])/4.0*Z[5]**-0.5)
        else:
            dSbdSref = 0.0
        dSbdSref2 = 2.0*S_shifted[0, 1]*dSbdSref
        dThetadSref = Ai[1]*dSbdSref + 0.5*Aij[1, 1]*dSbdSref2 \
            + Aij[0, 1]*S_shifted[0, 0]*dSbdSref \
            + Aij[2, 1]*S_shifted[0, 2]*dSbdSref \
            + Aij[3, 1]*S_shifted[0, 3]*dSbdSref

        J['Theta', 'z'] = np.array([np.append(dThetadtc/self.scalers['Theta'],
                                     [dThetadh/self.scalers['Theta'],
                                     dThetadM/self.scalers['Theta'],
                                     dThetadAR/self.scalers['Theta'],
                                     dThetadLambda/self.scalers['Theta'],
                                     dThetadSref/self.scalers['Theta']])])*self.scalers['z']
        if L/self.pf.d['twist'][3]>=0.75 and L/self.pf.d['twist'][3]<=1.25:							 
            dSLdL = 1.0/self.pf.d['twist'][3]
        else:
            dSLdL = 0.0
        dSLdL2 = 2.0*S_shifted[0, 3]*dSLdL
        dThetadL = Ai[3]*dSLdL + 0.5*Aij[3, 3]*dSLdL2 \
            + Aij[0, 3]*S_shifted[0, 0]*dSLdL \
            + Aij[1, 3]*S_shifted[0, 1]*dSLdL \
            + Aij[2, 3]*S_shifted[0, 2]*dSLdL
        J['Theta', 'L'] = (np.array([[dThetadL]]) \
                           / self.scalers['Theta']*self.scalers['L']).reshape((1, 1))
        dThetadWE = 0.0
        J['Theta', 'WE'] = np.array([[dThetadWE]])/self.scalers['Theta']*self.scalers['WE']

        # dsigma #############################################################
        b = np.sqrt(abs(Z[5]*Z[3]))/2.0
        R = (1.0+2.0*Xstr[0])/(3.0*(1.0+Xstr[0]))
        s_new = [Z[0], L, Xstr[1], b, R]
        S_shifted, Ai, Aij = self.pf(s_new,
                                          [4, 1, 4, 1, 1], [0.1]*5,
                                          "sigma[1]", deriv=True)
        if R/self.pf.d['sigma[1]'][4]>=0.75 and R/self.pf.d['sigma[1]'][4]<=1.25:								  
            dSRdlambda = 1.0/self.pf.d['sigma[1]'][4]*1.0/(3.0*(1.0+Xstr[0])**2)
        else:
            dSRdlambda = 0.0
        dSRdlambda2 = 2.0*S_shifted[0, 4]*dSRdlambda
        dsigma1dlambda = Ai[4]*dSRdlambda + 0.5*Aij[4, 4]*dSRdlambda2 \
            + Aij[0, 4]*S_shifted[0, 0]*dSRdlambda \
            + Aij[1, 4]*S_shifted[0, 1]*dSRdlambda \
            + Aij[2, 4]*S_shifted[0, 2]*dSRdlambda \
            + Aij[3, 4]*S_shifted[0, 3]*dSRdlambda
        if Xstr[1]/self.pf.d['sigma[1]'][2]>=0.75 and Xstr[1]/self.pf.d['sigma[1]'][2]<=1.25:
            dSxdx = 1.0/self.pf.d['sigma[1]'][2]
        else:
            dSxdx = 0.0
        dSxdx2 = 2.0*S_shifted[0, 2]*dSxdx
        dsigma1dx = Ai[2]*dSxdx+0.5*Aij[2, 2]*dSxdx2 \
            + Aij[0, 2]*S_shifted[0, 0]*dSxdx \
            + Aij[1, 2]*S_shifted[0, 1]*dSxdx \
            + Aij[3, 2]*S_shifted[0, 3]*dSxdx \
            + Aij[4, 2]*S_shifted[0, 4]*dSxdx

        S_shifted, Ai, Aij = self.pf(s_new,
                                          [4, 1, 4, 1, 1], [0.15]*5,
                                          "sigma[2]", deriv=True)										  
        if R/self.pf.d['sigma[2]'][4]>=0.75 and R/self.pf.d['sigma[2]'][4]<=1.25:								  
            dSRdlambda = 1.0/self.pf.d['sigma[2]'][4]*1.0/(3.0*(1.0+Xstr[0])**2)
        else:
            dSRdlambda = 0.0
        dSRdlambda2 = 2.0*S_shifted[0, 4]*dSRdlambda
        dsigma2dlambda = Ai[4]*dSRdlambda \
            + 0.5*Aij[4, 4]*dSRdlambda2 \
            + Aij[0, 4]*S_shifted[0, 0]*dSRdlambda \
            + Aij[1, 4]*S_shifted[0, 1]*dSRdlambda \
            + Aij[2, 4]*S_shifted[0, 2]*dSRdlambda \
            + Aij[3, 4]*S_shifted[0, 3]*dSRdlambda
        if Xstr[1]/self.pf.d['sigma[2]'][2]>=0.75 and Xstr[1]/self.pf.d['sigma[2]'][2]<=1.25:
            dSxdx = 1.0/self.pf.d['sigma[2]'][2]
        else:
            dSxdx = 0.0
        dSxdx2 = 2.0*S_shifted[0, 2]*dSxdx
        dsigma2dx = Ai[2]*dSxdx + 0.5*Aij[2, 2]*dSxdx2 \
            + Aij[0, 2]*S_shifted[0, 0]*dSxdx \
            + Aij[1, 2]*S_shifted[0, 1]*dSxdx \
            + Aij[3, 2]*S_shifted[0, 3]*dSxdx \
            + Aij[4, 2]*S_shifted[0, 4]*dSxdx

        S_shifted, Ai, Aij = self.pf(s_new,
                                          [4, 1, 4, 1, 1], [0.2]*5,
                                          "sigma[3]", deriv=True)
        if R/self.pf.d['sigma[3]'][4]>=0.75 and R/self.pf.d['sigma[3]'][4]<=1.25:								  
            dSRdlambda = 1.0/self.pf.d['sigma[3]'][4]*1.0/(3.0*(1.0+Xstr[0])**2)
        else:
            dSRdlambda = 0.0
        dSRdlambda2 = 2.0*S_shifted[0, 4]*dSRdlambda
        dsigma3dlambda = Ai[4]*dSRdlambda+0.5*Aij[4, 4]*dSRdlambda2 \
            + Aij[0, 4]*S_shifted[0, 0]*dSRdlambda \
            + Aij[1, 4]*S_shifted[0, 1]*dSRdlambda \
            + Aij[2, 4]*S_shifted[0, 2]*dSRdlambda \
            + Aij[3, 4]*S_shifted[0, 3]*dSRdlambda
        if Xstr[1]/self.pf.d['sigma[3]'][2]>=0.75 and Xstr[1]/self.pf.d['sigma[3]'][2]<=1.25:
            dSxdx = 1.0/self.pf.d['sigma[3]'][2]
        else:
            dSxdx = 0.0
        dSxdx2 = 2.0*S_shifted[0, 2]*dSxdx
        dsigma3dx = Ai[2]*dSxdx+0.5*Aij[2, 2]*dSxdx2 \
            + Aij[0, 2]*S_shifted[0, 0]*dSxdx \
            + Aij[1, 2]*S_shifted[0, 1]*dSxdx \
            + Aij[3, 2]*S_shifted[0, 3]*dSxdx \
            + Aij[4, 2]*S_shifted[0, 4]*dSxdx

        S_shifted, Ai, Aij = self.pf(s_new,
                                          [4, 1, 4, 1, 1], [0.25]*5,
                                          "sigma[4]", deriv=True)
        if R/self.pf.d['sigma[4]'][4]>=0.75 and R/self.pf.d['sigma[4]'][4]<=1.25:								  
            dSRdlambda = 1.0/self.pf.d['sigma[4]'][4]*1.0/(3.0*(1.0+Xstr[0])**2)
        else:
            dSRdlambda = 0.0
        dSRdlambda2 = 2.0*S_shifted[0, 4]*dSRdlambda
        dsigma4dlambda = Ai[4]*dSRdlambda \
            + 0.5*Aij[4, 4]*dSRdlambda2 \
            + Aij[0, 4]*S_shifted[0, 0]*dSRdlambda \
            + Aij[1, 4]*S_shifted[0, 1]*dSRdlambda \
            + Aij[2, 4]*S_shifted[0, 2]*dSRdlambda \
            + Aij[3, 4]*S_shifted[0, 3]*dSRdlambda
        if Xstr[1]/self.pf.d['sigma[4]'][2]>=0.75 and Xstr[1]/self.pf.d['sigma[4]'][2]<=1.25:
            dSxdx = 1.0/self.pf.d['sigma[4]'][2]
        else:
            dSxdx = 0.0
        dSxdx2 = 2.0*S_shifted[0, 2]*dSxdx
        dsigma4dx = Ai[2]*dSxdx+0.5*Aij[2, 2]*dSxdx2 \
            + Aij[0, 2]*S_shifted[0, 0]*dSxdx \
            + Aij[1, 2]*S_shifted[0, 1]*dSxdx \
            + Aij[3, 2]*S_shifted[0, 3]*dSxdx \
            + Aij[4, 2]*S_shifted[0, 4]*dSxdx
        S_shifted, Ai, Aij = self.pf(s_new,
                                          [4, 1, 4, 1, 1], [0.3]*5,
                                          "sigma[5]", deriv=True)
        if R/self.pf.d['sigma[5]'][4]>=0.75 and R/self.pf.d['sigma[5]'][4]<=1.25:								  
            dSRdlambda = 1.0/self.pf.d['sigma[5]'][4]*1.0/(3.0*(1.0+Xstr[0])**2)
        else:
            dSRdlambda = 0.0
        dSRdlambda2 = 2.0*S_shifted[0, 4]*dSRdlambda
        dsigma5dlambda = Ai[4]*dSRdlambda+0.5*Aij[4, 4]*dSRdlambda2 \
            + Aij[0, 4]*S_shifted[0, 0]*dSRdlambda \
            + Aij[1, 4]*S_shifted[0, 1]*dSRdlambda \
            + Aij[2, 4]*S_shifted[0, 2]*dSRdlambda \
            + Aij[3, 4]*S_shifted[0, 3]*dSRdlambda
        if Xstr[1]/self.pf.d['sigma[5]'][2]>=0.75 and Xstr[1]/self.pf.d['sigma[5]'][2]<=1.25:
            dSxdx = 1.0/self.pf.d['sigma[5]'][2]
        else:
            dSxdx = 0.0
        dSxdx2 = 2.0*S_shifted[0, 2]*dSxdx
        dsigma5dx = Ai[2]*dSxdx + 0.5*Aij[2, 2]*dSxdx2 \
            + Aij[0, 2]*S_shifted[0, 0]*dSxdx \
            + Aij[1, 2]*S_shifted[0, 1]*dSxdx \
            + Aij[3, 2]*S_shifted[0, 3]*dSxdx \
            + Aij[4, 2]*S_shifted[0, 4]*dSxdx

        J['sigma', 'x_str'] = np.array(
            [[dsigma1dlambda[0, 0]/self.scalers['sigma'][0],
              dsigma1dx[0, 0]/self.scalers['sigma'][0]],
             [dsigma2dlambda[0, 0]/self.scalers['sigma'][1],
              dsigma2dx[0, 0]/self.scalers['sigma'][1]],
             [dsigma3dlambda[0, 0]/self.scalers['sigma'][2],
              dsigma3dx[0, 0]/self.scalers['sigma'][2]],
             [dsigma4dlambda[0, 0]/self.scalers['sigma'][3],
              dsigma4dx[0, 0]/self.scalers['sigma'][3]],
             [dsigma5dlambda[0, 0]/self.scalers['sigma'][4],
              dsigma5dx[0, 0]/self.scalers['sigma'][4]]])*self.scalers['x_str']

        S_shifted, Ai, Aij = self.pf(s_new,
                                          [4, 1, 4, 1, 1], [0.1]*5,
                                          "sigma[1]", deriv=True)
        if Z[0]/self.pf.d['sigma[1]'][0]>=0.75 and Z[0]/self.pf.d['sigma[1]'][0]<=1.25: 					  
            dStcdtc = 1.0/self.pf.d['sigma[1]'][0]
        else:
            dStcdtc = 0.0
        dStcdtc2 = 2.0*S_shifted[0, 0]*dStcdtc
        dsigma1dtc = Ai[0]*dStcdtc+0.5*Aij[0, 0]*dStcdtc2 \
            + Aij[1, 0]*S_shifted[0, 1]*dStcdtc \
            + Aij[2, 0]*S_shifted[0, 2]*dStcdtc \
            + Aij[3, 0]*S_shifted[0, 3]*dStcdtc \
            + Aij[4, 0]*S_shifted[0, 4]*dStcdtc
        dsigma1dh = 0.0
        dsigma1dM = 0.0
        if b/self.pf.d['sigma[1]'][3]>=0.75 and b/self.pf.d['sigma[1]'][3]<=1.25: 
            dSbdAR = 1.0/self.pf.d['sigma[1]'][3]*(np.sqrt(Z[5])/4.0*Z[3]**-0.5)
            dSbdSref = 1.0/self.pf.d['sigma[1]'][3]*(np.sqrt(Z[3])/4.0*Z[5]**-0.5)
        else:
            dSbdAR = 0.0
            dSbdSref =0.0
        dSbdAR2 = 2.0*S_shifted[0, 3]*dSbdAR
        dsigma1dAR = Ai[3]*dSbdAR+0.5*Aij[3, 3]*dSbdAR2 \
            + Aij[0, 3]*S_shifted[0, 0]*dSbdAR \
            + Aij[1, 3]*S_shifted[0, 1]*dSbdAR \
            + Aij[2, 3]*S_shifted[0, 2]*dSbdAR \
            + Aij[4, 3]*S_shifted[0, 4]*dSbdAR
        dsigma1dLambda = 0.0
        dSbdSref2 = 2.0*S_shifted[0, 3]*dSbdSref
        dsigma1dSref = Ai[3]*dSbdSref + 0.5*Aij[3, 3]*dSbdSref2 \
            + Aij[0, 3]*S_shifted[0, 0]*dSbdSref \
            + Aij[1, 3]*S_shifted[0, 1]*dSbdSref \
            + Aij[2, 3]*S_shifted[0, 2]*dSbdSref \
            + Aij[4, 3]*S_shifted[0, 4]*dSbdSref
        S_shifted, Ai, Aij = self.pf(s_new,
                                          [4, 1, 4, 1, 1], [0.15]*5,
                                          "sigma[2]", deriv=True)
										  
        if Z[0]/self.pf.d['sigma[2]'][0]>=0.75 and Z[0]/self.pf.d['sigma[2]'][0]<=1.25: 					  
            dStcdtc = 1.0/self.pf.d['sigma[2]'][0]
        else:
            dStcdtc = 0.0
        dStcdtc2 = 2.0*S_shifted[0, 0]*dStcdtc
        dsigma2dtc = Ai[0]*dStcdtc+0.5*Aij[0, 0]*dStcdtc2 \
            + Aij[1, 0]*S_shifted[0, 1]*dStcdtc \
            + Aij[2, 0]*S_shifted[0, 2]*dStcdtc \
            + Aij[3, 0]*S_shifted[0, 3]*dStcdtc \
            + Aij[4, 0]*S_shifted[0, 4]*dStcdtc
        dsigma2dh = 0.0
        dsigma2dM = 0.0
        if b/self.pf.d['sigma[2]'][3]>=0.75 and b/self.pf.d['sigma[2]'][3]<=1.25: 
            dSbdAR = 1.0/self.pf.d['sigma[2]'][3]*(np.sqrt(Z[5])/4.0*Z[3]**-0.5)
            dSbdSref = 1.0/self.pf.d['sigma[2]'][3]*(np.sqrt(Z[3])/4.0*Z[5]**-0.5)
        else:
            dSbdAR = 0.0
            dSbdSref =0.0
        dSbdAR2 = 2.0*S_shifted[0, 3]*dSbdAR
        dsigma2dAR = Ai[3]*dSbdAR+0.5*Aij[3, 3]*dSbdAR2 \
            + Aij[0, 3]*S_shifted[0, 0]*dSbdAR \
            + Aij[1, 3]*S_shifted[0, 1]*dSbdAR \
            + Aij[2, 3]*S_shifted[0, 2]*dSbdAR \
            + Aij[4, 3]*S_shifted[0, 4]*dSbdAR
        dsigma2dLambda = 0.0
        dSbdSref2 = 2.0*S_shifted[0, 3]*dSbdSref
        dsigma2dSref = Ai[3]*dSbdSref + 0.5*Aij[3, 3]*dSbdSref2 \
            + Aij[0, 3]*S_shifted[0, 0]*dSbdSref \
            + Aij[1, 3]*S_shifted[0, 1]*dSbdSref \
            + Aij[2, 3]*S_shifted[0, 2]*dSbdSref \
            + Aij[4, 3]*S_shifted[0, 4]*dSbdSref

        S_shifted, Ai, Aij = self.pf(s_new,
                                          [4, 1, 4, 1, 1], [0.20]*5,
                                          "sigma[3]", deriv=True)
        if Z[0]/self.pf.d['sigma[3]'][0]>=0.75 and Z[0]/self.pf.d['sigma[3]'][0]<=1.25: 					  
            dStcdtc = 1.0/self.pf.d['sigma[3]'][0]
        else:
            dStcdtc = 0.0
        dStcdtc2 = 2.0*S_shifted[0, 0]*dStcdtc
        dsigma3dtc = Ai[0]*dStcdtc+0.5*Aij[0, 0]*dStcdtc2 \
            + Aij[1, 0]*S_shifted[0, 1]*dStcdtc \
            + Aij[2, 0]*S_shifted[0, 2]*dStcdtc \
            + Aij[3, 0]*S_shifted[0, 3]*dStcdtc \
            + Aij[4, 0]*S_shifted[0, 4]*dStcdtc
        dsigma3dh = 0.0
        dsigma3dM = 0.0
        if b/self.pf.d['sigma[3]'][3]>=0.75 and b/self.pf.d['sigma[3]'][3]<=1.25: 
            dSbdAR = 1.0/self.pf.d['sigma[3]'][3]*(np.sqrt(Z[5])/4.0*Z[3]**-0.5)
            dSbdSref = 1.0/self.pf.d['sigma[3]'][3]*(np.sqrt(Z[3])/4.0*Z[5]**-0.5)
        else:
            dSbdAR = 0.0
            dSbdSref =0.0
        dSbdAR2 = 2.0*S_shifted[0, 3]*dSbdAR
        dsigma3dAR = Ai[3]*dSbdAR+0.5*Aij[3, 3]*dSbdAR2 \
            + Aij[0, 3]*S_shifted[0, 0]*dSbdAR \
            + Aij[1, 3]*S_shifted[0, 1]*dSbdAR \
            + Aij[2, 3]*S_shifted[0, 2]*dSbdAR \
            + Aij[4, 3]*S_shifted[0, 4]*dSbdAR
        dsigma3dLambda = 0.0
        dSbdSref2 = 2.0*S_shifted[0, 3]*dSbdSref
        dsigma3dSref = Ai[3]*dSbdSref+0.5*Aij[3, 3]*dSbdSref2 \
            + Aij[0, 3]*S_shifted[0, 0]*dSbdSref \
            + Aij[1, 3]*S_shifted[0, 1]*dSbdSref \
            + Aij[2, 3]*S_shifted[0, 2]*dSbdSref \
            + Aij[4, 3]*S_shifted[0, 4]*dSbdSref

        S_shifted, Ai, Aij = self.pf(s_new,
                                          [4, 1, 4, 1, 1], [0.25]*5,
                                          "sigma[4]", deriv=True)
        if Z[0]/self.pf.d['sigma[4]'][0]>=0.75 and Z[0]/self.pf.d['sigma[4]'][0]<=1.25: 					  
            dStcdtc = 1.0/self.pf.d['sigma[4]'][0]
        else:
            dStcdtc = 0.0
        dStcdtc2 = 2.0*S_shifted[0, 0]*dStcdtc
        dsigma4dtc = Ai[0]*dStcdtc+0.5*Aij[0, 0]*dStcdtc2 \
            + Aij[1, 0]*S_shifted[0, 1]*dStcdtc \
            + Aij[2, 0]*S_shifted[0, 2]*dStcdtc \
            + Aij[3, 0]*S_shifted[0, 3]*dStcdtc \
            + Aij[4, 0]*S_shifted[0, 4]*dStcdtc
        dsigma4dh = 0.0
        dsigma4dM = 0.0
        if b/self.pf.d['sigma[4]'][3]>=0.75 and b/self.pf.d['sigma[4]'][3]<=1.25: 
            dSbdAR = 1.0/self.pf.d['sigma[4]'][3]*(np.sqrt(Z[5])/4.0*Z[3]**-0.5)
            dSbdSref = 1.0/self.pf.d['sigma[4]'][3]*(np.sqrt(Z[3])/4.0*Z[5]**-0.5)
        else:
            dSbdAR = 0.0
            dSbdSref =0.0
        dSbdAR2 = 2.0*S_shifted[0, 3]*dSbdAR
        dsigma4dAR = Ai[3]*dSbdAR + 0.5*Aij[3, 3]*dSbdAR2 \
            + Aij[0, 3]*S_shifted[0, 0]*dSbdAR \
            + Aij[1, 3]*S_shifted[0, 1]*dSbdAR \
            + Aij[2, 3]*S_shifted[0, 2]*dSbdAR \
            + Aij[4, 3]*S_shifted[0, 4]*dSbdAR
        dsigma4dLambda = 0.0
        dSbdSref2 = 2.0*S_shifted[0, 3]*dSbdSref
        dsigma4dSref = Ai[3]*dSbdSref + 0.5*Aij[3, 3]*dSbdSref2 \
            + Aij[0, 3]*S_shifted[0, 0]*dSbdSref \
            + Aij[1, 3]*S_shifted[0, 1]*dSbdSref \
            + Aij[2, 3]*S_shifted[0, 2]*dSbdSref \
            + Aij[4, 3]*S_shifted[0, 4]*dSbdSref

        S_shifted, Ai, Aij = self.pf(s_new,
                                          [4, 1, 4, 1, 1], [0.3]*5,
                                          "sigma[5]", deriv=True)
        if Z[0]/self.pf.d['sigma[5]'][0]>=0.75 and Z[0]/self.pf.d['sigma[5]'][0]<=1.25: 					  
            dStcdtc = 1.0/self.pf.d['sigma[5]'][0]
        else:
            dStcdtc = 0.0
        dStcdtc2 = 2.0*S_shifted[0, 0]*dStcdtc
        dsigma5dtc = Ai[0]*dStcdtc+0.5*Aij[0, 0]*dStcdtc2 \
            + Aij[1, 0]*S_shifted[0, 1]*dStcdtc \
            + Aij[2, 0]*S_shifted[0, 2]*dStcdtc \
            + Aij[3, 0]*S_shifted[0, 3]*dStcdtc \
            + Aij[4, 0]*S_shifted[0, 4]*dStcdtc
        dsigma5dh = 0.0
        dsigma5dM = 0.0
        if b/self.pf.d['sigma[5]'][3]>=0.75 and b/self.pf.d['sigma[5]'][3]<=1.25: 
            dSbdAR = 1.0/self.pf.d['sigma[5]'][3]*(np.sqrt(Z[5])/4.0*Z[3]**-0.5)
            dSbdSref = 1.0/self.pf.d['sigma[5]'][3]*(np.sqrt(Z[3])/4.0*Z[5]**-0.5)
        else:
            dSbdAR = 0.0
            dSbdSref =0.0
        dSbdAR2 = 2.0*S_shifted[0, 3]*dSbdAR
        dsigma5dAR = Ai[3]*dSbdAR + 0.5*Aij[3, 3]*dSbdAR2 \
            + Aij[0, 3]*S_shifted[0, 0]*dSbdAR \
            + Aij[1, 3]*S_shifted[0, 1]*dSbdAR \
            + Aij[2, 3]*S_shifted[0, 2]*dSbdAR \
            + Aij[4, 3]*S_shifted[0, 4]*dSbdAR
        dsigma5dLambda = 0.0
        dSbdSref2 = 2.0*S_shifted[0, 3]*dSbdSref
        dsigma5dSref = Ai[3]*dSbdSref + 0.5*Aij[3, 3]*dSbdSref2 \
            + Aij[0, 3]*S_shifted[0, 0]*dSbdSref \
            + Aij[1, 3]*S_shifted[0, 1]*dSbdSref \
            + Aij[2, 3]*S_shifted[0, 2]*dSbdSref \
            + Aij[4, 3]*S_shifted[0, 4]*dSbdSref

        J['sigma', 'z'] = np.array(
            [[dsigma1dtc[0, 0]/self.scalers['sigma'][0],
              dsigma1dh/self.scalers['sigma'][0],
              dsigma1dM/self.scalers['sigma'][0],
              dsigma1dAR[0, 0]/self.scalers['sigma'][0],
              dsigma1dLambda/self.scalers['sigma'][0],
              dsigma1dSref[0, 0]/self.scalers['sigma'][0]],
             [dsigma2dtc[0, 0]/self.scalers['sigma'][1],
              dsigma2dh/self.scalers['sigma'][1],
              dsigma2dM/self.scalers['sigma'][1],
              dsigma2dAR[0, 0]/self.scalers['sigma'][1],
              dsigma2dLambda/self.scalers['sigma'][1],
              dsigma2dSref[0, 0]/self.scalers['sigma'][1]],
             [dsigma3dtc[0, 0]/self.scalers['sigma'][2],
              dsigma3dh/self.scalers['sigma'][2],
              dsigma3dM/self.scalers['sigma'][2],
              dsigma3dAR[0, 0]/self.scalers['sigma'][2],
              dsigma3dLambda/self.scalers['sigma'][2],
              dsigma3dSref[0, 0]/self.scalers['sigma'][2]],
             [dsigma4dtc[0, 0]/self.scalers['sigma'][3],
              dsigma4dh/self.scalers['sigma'][3],
              dsigma4dM/self.scalers['sigma'][3],
              dsigma4dAR[0, 0]/self.scalers['sigma'][3],
              dsigma4dLambda/self.scalers['sigma'][3],
              dsigma4dSref[0, 0]/self.scalers['sigma'][3]],
             [dsigma5dtc[0, 0]/self.scalers['sigma'][4],
              dsigma5dh/self.scalers['sigma'][4],
              dsigma5dM/self.scalers['sigma'][4],
              dsigma5dAR[0, 0]/self.scalers['sigma'][4],
              dsigma5dLambda/self.scalers['sigma'][4],
              dsigma5dSref[0, 0]/self.scalers['sigma'][4]]])*self.scalers['z']

        # dS #################################################################
        S_shifted, Ai, Aij = self.pf([Z[0], L, Xstr[1], b, R],
                                          [4, 1, 4, 1, 1], [0.1]*5,
                                          "sigma[1]", deriv=True)
        if L/self.pf.d['sigma[1]'][1]>=0.75 and L/self.pf.d['sigma[1]'][1]<=1.25:							  
            dSLdL = 1.0/self.pf.d['sigma[1]'][1]
        else:
            dSLdL = 0.0
        dSLdL2 = 2.0*S_shifted[0, 1]*dSLdL
        dsigma1dL = Ai[1]*dSLdL + 0.5*Aij[1, 1]*dSLdL2 \
            + Aij[0, 1]*S_shifted[0, 0]*dSLdL \
            + Aij[2, 1]*S_shifted[0, 2]*dSLdL \
            + Aij[3, 1]*S_shifted[0, 3]*dSLdL \
            + Aij[4, 1]*S_shifted[0, 4]*dSLdL

        S_shifted, Ai, Aij = self.pf(s_new,
                                          [4, 1, 4, 1, 1], [0.15]*5,
                                          "sigma[2]", deriv=True)
        if L/self.pf.d['sigma[2]'][1]>=0.75 and L/self.pf.d['sigma[2]'][1]<=1.25:							  
            dSLdL = 1.0/self.pf.d['sigma[2]'][1]
        else:
            dSLdL = 0.0
        dSLdL2 = 2.0*S_shifted[0, 1]*dSLdL
        dsigma2dL = Ai[1]*dSLdL+0.5*Aij[1, 1]*dSLdL2 \
            + Aij[0, 1]*S_shifted[0, 0]*dSLdL \
            + Aij[2, 1]*S_shifted[0, 2]*dSLdL \
            + Aij[3, 1]*S_shifted[0, 3]*dSLdL \
            + Aij[4, 1]*S_shifted[0, 4]*dSLdL

        S_shifted, Ai, Aij = self.pf(s_new,
                                          [4, 1, 4, 1, 1], [0.2]*5,
                                          "sigma[3]", deriv=True)
        if L/self.pf.d['sigma[3]'][1]>=0.75 and L/self.pf.d['sigma[3]'][1]<=1.25:							  
            dSLdL = 1.0/self.pf.d['sigma[3]'][1]
        else:
            dSLdL = 0.0
        dSLdL2 = 2.0*S_shifted[0, 1]*dSLdL
        dsigma3dL = Ai[1]*dSLdL + 0.5*Aij[1, 1]*dSLdL2 \
            + Aij[0, 1]*S_shifted[0, 0]*dSLdL \
            + Aij[2, 1]*S_shifted[0, 2]*dSLdL \
            + Aij[3, 1]*S_shifted[0, 3]*dSLdL \
            + Aij[4, 1]*S_shifted[0, 4]*dSLdL

        S_shifted, Ai, Aij = self.pf(s_new,
                                          [4, 1, 4, 1, 1], [0.25]*5,
                                          "sigma[4]", deriv=True)
        if L/self.pf.d['sigma[4]'][1]>=0.75 and L/self.pf.d['sigma[4]'][1]<=1.25:							  
            dSLdL = 1.0/self.pf.d['sigma[4]'][1]
        else:
            dSLdL = 0.0
        dSLdL2 = 2.0*S_shifted[0, 1]*dSLdL
        dsigma4dL = Ai[1]*dSLdL + 0.5*Aij[1, 1]*dSLdL2 \
            + Aij[0, 1]*S_shifted[0, 0]*dSLdL \
            + Aij[2, 1]*S_shifted[0, 2]*dSLdL \
            + Aij[3, 1]*S_shifted[0, 3]*dSLdL \
            + Aij[4, 1]*S_shifted[0, 4]*dSLdL

        S_shifted, Ai, Aij = self.pf(s_new,
                                          [4, 1, 4, 1, 1], [0.3]*5,
                                          "sigma[5]", deriv=True)
        if L/self.pf.d['sigma[5]'][1]>=0.75 and L/self.pf.d['sigma[5]'][1]<=1.25:							  
            dSLdL = 1.0/self.pf.d['sigma[5]'][1]
        else:
            dSLdL = 0.0
        dSLdL2 = 2.0*S_shifted[0, 1]*dSLdL
        dsigma5dL = Ai[1]*dSLdL + 0.5*Aij[1, 1]*dSLdL2 \
            + Aij[0, 1]*S_shifted[0, 0]*dSLdL \
            + Aij[2, 1]*S_shifted[0, 2]*dSLdL \
            + Aij[3, 1]*S_shifted[0, 3]*dSLdL \
            + Aij[4, 1]*S_shifted[0, 4]*dSLdL

        J['sigma','L'] = np.array(
            [[dsigma1dL/self.scalers['sigma'][0]*self.scalers['L']],
             [dsigma2dL/self.scalers['sigma'][1]*self.scalers['L']],
             [dsigma3dL/self.scalers['sigma'][2]*self.scalers['L']],
             [dsigma4dL/self.scalers['sigma'][3]*self.scalers['L']],
             [dsigma5dL/self.scalers['sigma'][4]*self.scalers['L']]]).reshape((5, 1))

        J['sigma','WE'] = np.zeros((5, 1))

if __name__ == "__main__": # pragma: no cover

    from openmdao.api import Problem, IndepVarComp
    scalers = {}
    scalers['z'] = np.array([0.05, 45000., 1.6, 5.5, 55.0, 1000.0])
    scalers['x_str'] = np.array([0.25, 1.0])
    scalers['L'] = 49909.58578
    scalers['Theta'] = 0.950978
    scalers['WF'] = 7306.20261
    scalers['WT'] = 49909.58578
    scalers['WE'] = 5748.915355
    scalers['sigma'] = np.array([1.12255, 1.08170213, 1.0612766,
                                 1.04902128, 1.04085106])
    top=Problem()
    top.model.add_subsystem('z_in', IndepVarComp('z',
                                      np.array([1.2  ,  1.333,  0.875,  0.45 ,  1.27 ,  1.5])),
                 promotes=['*'])
    top.model.add_subsystem('x_str_in', IndepVarComp('x_str', np.array([1.6, 0.75])),
                 promotes=['*'])
    top.model.add_subsystem('L_in', IndepVarComp('L', 0.888), promotes=['*'])
    top.model.add_subsystem('WE_in', IndepVarComp('WE', 1.49), promotes=['*'])
    top.model.add_subsystem('Str1', Structure(scalers), promotes=['*'])
    top.setup()
    top.check_partials(compact_print=True)
