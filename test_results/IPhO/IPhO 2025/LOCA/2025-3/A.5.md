# Refined Solution
### Problem Statement Explanation
This problem asks for the radius, \(a_{H_{\ell}}\), of a champagne bubble when it reaches the free surface after rising a vertical distance \(H_{\ell}\) from the bottom of a glass.

The physical process involves a bubble that is simultaneously rising and growing. The following information and assumptions are provided or derived from previous parts of the problem:
*   **Bubble Motion**: The bubble rises vertically. At any instant, it is assumed to be moving at its terminal velocity, \(v\), which depends on its current radius, \(a\).
*   **Bubble Growth**: The bubble's radius, \(a\), increases with time. The rate of growth, \(q_a = \frac{da}{dt}\), is assumed to be constant.
*   **Initial and Final Conditions**: The bubble starts with an initial radius \(a_0\) at height \(z=0\) and reaches a final radius \(a_{H_{\ell}}\) at height \(z=H_{\ell}\). We are given the assumption that the final radius is much larger than the initial one, i.e., \(a_{H_{\ell}} \gg a_0\).

The relevant variables and constants are:
*   \(a(t)\): The radius of the bubble at time \(t\).
*   \(v(a)\): The terminal velocity of the bubble as a function of its radius \(a\).
*   \(q_a = \frac{da}{dt}\): The constant rate of change of the bubble's radius. From Fig. 2, \(q_a = 0.23 \, \text{mm/s} = 2.3 \times 10^{-4} \, \text{m/s}\).
*   \(H_{\ell}\): The total height the bubble travels, given as \(10 \, \text{cm} = 0.1 \, \text{m}\).
*   \(\rho_{\ell}\): The density of the liquid (champagne), given as \(1.0 \times 10^3 \, \text{kg} \cdot \text{m}^{-3}\).
*   \(\rho_{gas}\): The density of the CO\(_2\) gas inside the bubble. We assume \(\rho_{gas} \ll \rho_{\ell}\).
*   \(\eta\): The dynamic viscosity of the liquid. From sub-problem A.4, its estimated value is \(\eta \approx 1.7 \times 10^{-3} \, \text{Pa} \cdot \text{s}\).
*   \(g_0\): The acceleration due to gravity, taken as \(9.8 \, \text{m} \cdot \text{s}^{-2}\).

The goal is to first derive a symbolic expression for \(a_{H_{\ell}}\) in terms of \(H_{\ell}\), \(q_a\), and the physical constants, and then to calculate its numerical value.

### Step 1: Relate the Bubble's Rise to its Growth
To find the final radius, we must connect the total height traveled, \(H_{\ell}\), to the change in the bubble's radius. We can do this by relating the differential elements of height, \(dz\), and radius, \(da\).

**Principles/Original Formulas/Assumptions**:
The velocity is the rate of change of position, and the growth rate is the rate of change of the radius.
\[
\boxed{v = \frac{dz}{dt}}
\]
\[
\boxed{q_a = \frac{da}{dt}}
\]
Using the chain rule, we can relate \(dz\) and \(da\).

**Derivation**:
From the definitions, we can write \(dz = v \, dt\) and \(dt = \frac{da}{q_a}\). Combining these gives a relationship between the infinitesimal change in height and the infinitesimal change in radius:
\[
\begin{align}
dz = v(a) \left(\frac{da}{q_a}\right)
\label{eq:dz_da} \tag{1}
\end{align}
\]
To find the total height \(H_{\ell}\), we integrate this expression from the initial state (radius \(a_0\) at height \(z=0\)) to the final state (radius \(a_{H_{\ell}}\) at height \(z=H_{\ell}\)).
\[
\begin{align}
H_{\ell} = \int_{0}^{H_{\ell}} dz = \int_{a_0}^{a_{H_{\ell}}} \frac{v(a)}{q_a} da
\label{eq:H_integral} \tag{2}
\end{align}
\]
This integral links the total height traveled to the bubble's growth and its velocity.

### Step 2: Substitute the Terminal Velocity and Integrate
Next, we use the expression for the terminal velocity \(v(a)\) derived in sub-problem A.4 and perform the integration.

**Principles/Original Formulas/Assumptions**:
The terminal velocity of the bubble, assuming Stokes' drag and balancing buoyant, gravitational, and drag forces, is:
\[
\boxed{v(a) = \frac{2 a^2 g_0 (\rho_{\ell} - \rho_{gas})}{9 \eta}}
\]
We use the approximation that the gas density is negligible compared to the liquid density:
\[
\boxed{\rho_{gas} \ll \rho_{\ell}}
\]

**Derivation**:
Applying the density approximation, the terminal velocity simplifies to:
\[
\begin{align}
v(a) \approx \frac{2 g_0 \rho_{\ell}}{9 \eta} a^2 = C a^2
\label{eq:v_approx} \tag{3}
\end{align}
\]
where we define the constant \(C = \frac{2 g_0 \rho_{\ell}}{9 \eta}\).
Substituting this expression for \(v(a)\) into the integral from Eq. \eqref{eq:H_integral}:
\[
\begin{align}
H_{\ell} &= \int_{a_0}^{a_{H_{\ell}}} \frac{C a^2}{q_a} da \nonumber \\
&= \frac{C}{q_a} \int_{a_0}^{a_{H_{\ell}}} a^2 da \nonumber \\
&= \frac{C}{q_a} \left[ \frac{a^3}{3} \right]_{a_0}^{a_{H_{\ell}}} \nonumber \\
&= \frac{C}{3q_a} (a_{H_{\ell}}^3 - a_0^3)
\label{eq:H_integrated} \tag{4}
\end{align}
\]

### Step 3: Solve for the Final Radius and Calculate its Value
We now solve for \(a_{H_{\ell}}\) using the given approximation and then substitute the numerical values to find the final answer.

**Principles/Original Formulas/Assumptions**:
The problem states to assume that the final radius is much larger than the initial radius.
\[
\boxed{a_{H_{\ell}} \gg a_0}
\]

**Derivation**:
The condition \(a_{H_{\ell}} \gg a_0\) implies \(a_{H_{\ell}}^3 \gg a_0^3\), so we can neglect the \(a_0^3\) term in Eq. \eqref{eq:H_integrated}:
\[
\begin{align}
H_{\ell} \approx \frac{C}{3q_a} a_{H_{\ell}}^3
\label{eq:H_approx} \tag{5}
\end{align}
\]
Solving for \(a_{H_{\ell}}^3\):
\[
\begin{align}
a_{H_{\ell}}^3 \approx \frac{3 q_a H_{\ell}}{C}
\label{eq:a_cubed_C} \tag{6}
\end{align}
\]
Substituting the expression for the constant \(C = \frac{2 g_0 \rho_{\ell}}{9 \eta}\):
\[
\begin{align}
a_{H_{\ell}}^3 &\approx \frac{3 q_a H_{\ell}}{\left( \frac{2 g_0 \rho_{\ell}}{9 \eta} \right)} = \frac{27 q_a H_{\ell} \eta}{2 g_0 \rho_{\ell}} \nonumber \\
a_{H_{\ell}} &= \left( \frac{27 q_a H_{\ell} \eta}{2 g_0 \rho_{\ell}} \right)^{1/3}
\label{eq:a_final_symbolic} \tag{7}
\end{align}
\]
Now, we perform the numerical calculation using the given values:
*   \(q_a = 2.3 \times 10^{-4} \, \text{m/s}\)
*   \(H_{\ell} = 0.1 \, \text{m}\)
*   \(\eta = 1.7 \times 10^{-3} \, \text{Pa} \cdot \text{s}\)
*   \(g_0 = 9.8 \, \text{m/s}^2\)
*   \(\rho_{\ell} = 1.0 \times 10^3 \, \text{kg/m}^3\)

Substituting these into Eq. \eqref{eq:a_final_symbolic}:
\[
\begin{align}
a_{H_{\ell}} &= \left( \frac{27 \times (2.3 \times 10^{-4}) \times (0.1) \times (1.7 \times 10^{-3})}{2 \times (9.8) \times (1.0 \times 10^3)} \right)^{1/3} \nonumber \\
&= \left( \frac{1.0557 \times 10^{-6}}{1.96 \times 10^4} \right)^{1/3} \, \text{m} \nonumber \\
&= \left( 5.3862 \times 10^{-11} \right)^{1/3} \, \text{m} \nonumber \\
&= \left( 53.862 \times 10^{-12} \right)^{1/3} \, \text{m} \nonumber \\
&\approx 3.776 \times 10^{-4} \, \text{m}
\label{eq:a_numerical} \tag{8}
\end{align}
\]
Rounding to two significant figures, consistent with the input data:
\[
\begin{align}
a_{H_{\ell}} \approx 3.8 \times 10^{-4} \, \text{m}
\end{align}
\]

### Final Answer
The expression for the radius of a bubble reaching the free surface is:
\[
\begin{align}
a_{H_{\ell}} = \left( \frac{27 q_a H_{\ell} \eta}{2 g_0 \rho_{\ell}} \right)^{1/3}
\end{align}
\]
The numerical value for the given parameters is:
\[
\begin{align}
\boxed{a_{H_{\ell}} \approx 3.8 \times 10^{-4} \, \text{m}}
\end{align}
\]