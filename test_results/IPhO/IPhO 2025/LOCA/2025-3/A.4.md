# Refined Solution
### Problem Statement Explanation
This problem asks for an analysis of a CO₂ bubble rising through a glass of champagne. We are given that the bubble moves at its terminal velocity. The tasks are to:
1.  Identify the main forces acting on a vertically rising bubble of radius \(a\).
2.  Derive an expression for the bubble's terminal velocity, \(v\), as a function of its radius, \(a\), which we denote as \(v(a)\).
3.  Provide a numerical estimate for the dynamic viscosity of champagne, \(\eta\), using data extracted from Fig. 3.

The relevant physical quantities and their given values are:
-   \(a\): The radius of the bubble. For the numerical estimation, a specific bubble has \(a = 0.19 \, \text{mm} = 1.9 \times 10^{-4} \, \text{m}\).
-   \(v\): The terminal velocity of the bubble. For the specific bubble, \(v = 4.5 \, \text{cm/s} = 4.5 \times 10^{-2} \, \text{m/s}\).
-   \(\rho_{\ell}\): The density of the liquid champagne, given as \(1.0 \times 10^{3} \, \text{kg} \cdot \text{m}^{-3}\).
-   \(\rho_{gas}\): The density of the CO₂ gas inside the bubble. This is much smaller than \(\rho_{\ell}\).
-   \(g_0\): The acceleration due to gravity. We will use the standard value \(g_0 = 9.81 \, \text{m/s}^2\).
-   \(\eta\): The dynamic viscosity of the liquid champagne, which we need to estimate.
-   \(F_B\), \(F_g\), \(F_D\): The buoyant, gravitational, and drag forces, respectively.

We make the following assumptions:
-   The bubble is a perfect sphere.
-   The bubble moves at a constant terminal velocity, implying the net force on it is zero.
-   The liquid (champagne) is stationary far from the bubble.
-   The drag force is described by Stokes' law, as given in the problem statement.

### Step 1: Identify the Forces on the Bubble
A bubble rising vertically in a liquid is subjected to three main forces. We define the upward direction as positive.

The principles governing these forces are:
1.  **Archimedes' Principle** for the buoyant force: The buoyant force on a submerged object is equal to the weight of the fluid it displaces.
    \[\boxed{F_B = \rho_{\text{fluid}} V_{\text{displaced}} g_0}\]
2.  **Gravitational Force**: The weight of an object is its mass times the gravitational acceleration.
    \[\boxed{F_g = m g_0}\]
3.  **Stokes' Law** for drag on a sphere (as given in the problem):
    \[\boxed{F_D = 6 \pi \eta a v}\]

Applying these principles to the bubble:
\[
\begin{align}
\text{1. Buoyant Force } (F_B): & \text{ This is an upward force. The volume of the spherical bubble is } V_b = \frac{4}{3}\pi a^3. \nonumber \\
& F_B = \rho_{\ell} V_b g_0 = \frac{4}{3}\pi a^3 \rho_{\ell} g_0 \quad (\text{upward}) \label{eq:Fb} \tag{1} \\
\text{2. Gravitational Force } (F_g): & \text{ This is a downward force, equal to the weight of the CO₂ gas inside the bubble.} \nonumber \\
& \text{The mass of the gas is } m_{gas} = \rho_{gas} V_b. \nonumber \\
& F_g = m_{gas} g_0 = \rho_{gas} V_b g_0 = \frac{4}{3}\pi a^3 \rho_{gas} g_0 \quad (\text{downward}) \label{eq:Fg} \tag{2} \\
\text{3. Drag Force } (F_D): & \text{ This is a downward force that opposes the bubble's upward motion.} \nonumber \\
& F_D = 6 \pi \eta a v \quad (\text{downward}) \label{eq:Fd} \tag{3}
\end{align}
\]

### Step 2: Derive the Terminal Velocity v(a)
The problem states that the bubble travels at its terminal velocity. This is a state of dynamic equilibrium where the net force on the bubble is zero.

The principle for this condition is Newton's First Law:
\[\boxed{\sum F_y = 0}\]

We apply this by balancing the upward and downward forces identified in Step 1.
\[
\begin{align}
\sum F_y &= F_B - F_g - F_D = 0 \label{eq:force_balance} \tag{4} \\
F_B &= F_g + F_D \nonumber \\
\frac{4}{3}\pi a^3 \rho_{\ell} g_0 &= \frac{4}{3}\pi a^3 \rho_{gas} g_0 + 6 \pi \eta a v \quad (\text{using eqs. \ref{eq:Fb}, \ref{eq:Fg}, \ref{eq:Fd}}) \label{eq:force_balance_sub} \tag{5}
\end{align}
\]
Now, we solve this equation for the terminal velocity \(v\).
\[
\begin{align}
6 \pi \eta a v &= \frac{4}{3}\pi a^3 g_0 (\rho_{\ell} - \rho_{gas}) \nonumber \\
v &= \frac{\frac{4}{3}\pi a^3 g_0 (\rho_{\ell} - \rho_{gas})}{6 \pi \eta a} \nonumber \\
v(a) &= \frac{2 a^2 g_0 (\rho_{\ell} - \rho_{gas})}{9 \eta} \label{eq:v_exact} \tag{6}
\end{align}
\]
The density of the liquid champagne is \(\rho_{\ell} = 1.0 \times 10^3 \, \text{kg} \cdot \text{m}^{-3}\). The density of CO₂ gas at atmospheric pressure is much smaller (given as \(\rho_{g} \approx 1.8 \, \text{kg} \cdot \text{m}^{-3}\) in Part B). Since \(\rho_{gas} \ll \rho_{\ell}\), we can make the accurate approximation \((\rho_{\ell} - \rho_{gas}) \approx \rho_{\ell}\).
\[
\begin{align}
v(a) \approx \frac{2 \rho_{\ell} g_0 a^2}{9 \eta} \label{eq:v_approx} \tag{7}
\end{align}
\]

### Step 3: Calculate the Dynamic Viscosity η
We use the expression for the terminal velocity derived in Step 2 to estimate the dynamic viscosity \(\eta\).

The governing relationship is the approximate formula for terminal velocity:
\[\boxed{v(a) \approx \frac{2 \rho_{\ell} g_0 a^2}{9 \eta}}\]

We rearrange this formula to solve for \(\eta\) and substitute the numerical values provided for a specific bubble in Fig. 3.
\[
\begin{align}
\eta &\approx \frac{2 \rho_{\ell} g_0 a^2}{9 v} \label{eq:eta_formula} \tag{8}
\end{align}
\]
The given values are:
-   Bubble radius: \(a = 0.19 \, \text{mm} = 1.9 \times 10^{-4} \, \text{m}\)
-   Bubble velocity: \(v = 4.5 \, \text{cm/s} = 4.5 \times 10^{-2} \, \text{m/s}\)
-   Liquid density: \(\rho_{\ell} = 1.0 \times 10^3 \, \text{kg} \cdot \text{m}^{-3}\)
-   Gravitational acceleration: \(g_0 = 9.81 \, \text{m} \cdot \text{s}^{-2}\)

Substituting these values into equation \eqref{eq:eta_formula}:
\[
\begin{align}
\eta &\approx \frac{2 \times (1.0 \times 10^3 \, \text{kg} \cdot \text{m}^{-3}) \times (9.81 \, \text{m} \cdot \text{s}^{-2}) \times (1.9 \times 10^{-4} \, \text{m})^2}{9 \times (4.5 \times 10^{-2} \, \text{m/s})} \nonumber \\
\eta &\approx \frac{2 \times 10^3 \times 9.81 \times 3.61 \times 10^{-8}}{0.405} \, \frac{(\text{kg} \cdot \text{m}^{-3}) \cdot (\text{m} \cdot \text{s}^{-2}) \cdot (\text{m}^2)}{\text{m/s}} \nonumber \\
\eta &\approx \frac{7.083 \times 10^{-4}}{0.405} \, \text{kg} \cdot \text{m}^{-1} \cdot \text{s}^{-1} \nonumber \\
\eta &\approx 1.749 \times 10^{-3} \, \text{kg} \cdot \text{m}^{-1} \cdot \text{s}^{-1} \label{eq:eta_calc} \tag{9}
\end{align}
\]
The unit \(\text{kg} \cdot \text{m}^{-1} \cdot \text{s}^{-1}\) is the SI unit for dynamic viscosity, also known as the Pascal-second (Pa·s). Rounding the result to two significant figures, consistent with the precision of the input data \(a\) and \(v\):
\[
\begin{align}
\eta \approx 1.7 \times 10^{-3} \, \text{Pa} \cdot \text{s} \label{eq:eta_final} \tag{10}
\end{align}
\]

### Final Answer
The main forces exerted on a vertically rising bubble are the upward buoyant force, the downward gravitational force, and the downward drag force. Their expressions are:
\[
\begin{align}
\text{Forces: } & F_B = \frac{4}{3}\pi a^3 \rho_{\ell} g_0 \text{ (upward)}, \\
& F_g = \frac{4}{3}\pi a^3 \rho_{gas} g_0 \text{ (downward)}, \\
& F_D = 6 \pi \eta a v \text{ (downward)}
\end{align}
\]
The expression for the terminal velocity \(v(a)\) is obtained by balancing these forces:
\[
\begin{align}
v(a) = \frac{2 a^2 g_0 (\rho_{\ell} - \rho_{gas})}{9 \eta}
\end{align}
\]
Using the provided data from Fig. 3 (\(a = 1.9 \times 10^{-4} \, \text{m}\), \(v = 4.5 \times 10^{-2} \, \text{m/s}\)) and the approximation \(\rho_{gas} \ll \rho_{\ell}\), the numerical estimate for the dynamic viscosity \(\eta\) is:
\[
\begin{align}
\boxed{ \eta \approx 1.7 \times 10^{-3} \, \text{Pa} \cdot \text{s} }
\end{align}
\]