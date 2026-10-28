# Coordinate geometry

## The coordinate plane

The Cartesian plane is made of two perpendicular number lines. The horizontal one is the x-axis and the vertical one is the y-axis. They meet at the origin, which has coordinates (0, 0).

A point is written as an ordered pair (x, y). The first number, the abscissa, says how far to move along the x-axis. The second number, the ordinate, says how far to move parallel to the y-axis. The order matters: (3, 2) and (2, 3) are different points.

The two axes divide the plane into four quadrants. Quadrant I has x positive and y positive. Quadrant II has x negative and y positive. Quadrant III has x negative and y negative. Quadrant IV has x positive and y negative. A point on an axis belongs to no quadrant.

A point on the x-axis has y equal to 0, written (x, 0). A point on the y-axis has x equal to 0, written (0, y). The reflection of (x, y) in the x-axis is (x, -y), in the y-axis is (-x, y), and in the origin is (-x, -y).

## Distance, midpoint and section formulas

The distance between two points (x1, y1) and (x2, y2) is the square root of (x2 - x1)^2 + (y2 - y1)^2. It comes from the Pythagoras theorem applied to the right triangle whose legs are the horizontal and vertical differences. For example, the distance between (1, 1) and (5, 4) is the square root of 16 + 9, which is 5.

The distance of the point (x, y) from the origin is the square root of x^2 + y^2.

The midpoint of the segment joining (x1, y1) and (x2, y2) is ((x1 + x2) / 2, (y1 + y2) / 2). Each coordinate of the midpoint is the average of the two end coordinates. The midpoint of (1, 2) and (7, 10) is (4, 6).

The section formula gives the point that divides the segment from (x1, y1) to (x2, y2) internally in the ratio m : n. It is ((m x2 + n x1) / (m + n), (m y2 + n y1) / (m + n)). When m = n it becomes the midpoint formula. For external division the denominator is m - n and the signs change.

The centroid of a triangle with vertices (x1, y1), (x2, y2) and (x3, y3) is ((x1 + x2 + x3) / 3, (y1 + y2 + y3) / 3). It divides every median in the ratio 2 : 1.

The area of a triangle with those vertices is half the absolute value of x1(y2 - y3) + x2(y3 - y1) + x3(y1 - y2). If this area is zero, the three points are collinear, which means they lie on one straight line.

## Slope of a line

The slope, or gradient, of a line is its steepness: the rise divided by the run. For two points (x1, y1) and (x2, y2) on the line, the slope m is (y2 - y1) / (x2 - x1), provided x1 and x2 are different.

If a line makes an angle theta with the positive x-axis, measured anticlockwise, its slope is m = tan(theta). A line that rises to the right has positive slope, a line that falls to the right has negative slope, a horizontal line has slope 0, and a vertical line has an undefined slope because the run is 0.

Two lines are parallel if and only if they have the same slope, m1 = m2. Two lines are perpendicular if and only if the product of their slopes is -1, m1 x m2 = -1, which means one slope is the negative reciprocal of the other. A line of slope 2 is perpendicular to a line of slope -1/2.

Three points A, B and C are collinear if the slope of AB equals the slope of BC.

## Equation of a straight line

A horizontal line has the equation y = k and a vertical line has the equation x = h. The x-axis is y = 0 and the y-axis is x = 0.

Slope-intercept form: y = mx + c. Here m is the slope and c is the y-intercept, the value of y where the line cuts the y-axis. The line y = 2x + 1 has slope 2 and cuts the y-axis at (0, 1).

Point-slope form: y - y1 = m(x - x1). It gives the line of slope m through the point (x1, y1).

Two-point form: (y - y1) = ((y2 - y1) / (x2 - x1)) (x - x1). It gives the line through the points (x1, y1) and (x2, y2).

Intercept form: x / a + y / b = 1. The line cuts the x-axis at (a, 0) and the y-axis at (0, b).

Normal form: x cos(alpha) + y sin(alpha) = p, where p is the perpendicular distance of the line from the origin and alpha is the angle that this perpendicular makes with the positive x-axis.

General form: Ax + By + C = 0, where A and B are not both zero. Its slope is -A / B and its y-intercept is -C / B. Every straight line can be written in this form.

## Angle between lines and distance from a line

The acute angle theta between two lines with slopes m1 and m2 satisfies tan(theta) = |(m1 - m2) / (1 + m1 m2)|. If 1 + m1 m2 = 0 the lines are perpendicular.

The perpendicular distance of the point (x1, y1) from the line Ax + By + C = 0 is |A x1 + B y1 + C| / the square root of (A^2 + B^2).

The distance between two parallel lines Ax + By + C1 = 0 and Ax + By + C2 = 0 is |C1 - C2| / the square root of (A^2 + B^2).

The point where two lines meet is found by solving their two equations together as simultaneous equations.

## The circle

A circle is the set of all points in a plane that are at a fixed distance, the radius, from a fixed point, the centre. The diameter is twice the radius.

Standard form: the circle with centre (h, k) and radius r has the equation (x - h)^2 + (y - k)^2 = r^2. When the centre is the origin it becomes x^2 + y^2 = r^2. The circle (x - 2)^2 + (y - 1)^2 = 9 has centre (2, 1) and radius 3.

General form: x^2 + y^2 + 2gx + 2fy + c = 0. Its centre is (-g, -f) and its radius is the square root of (g^2 + f^2 - c). The equation represents a real circle only when g^2 + f^2 - c is positive.

The circle that has the points (x1, y1) and (x2, y2) as the ends of a diameter has the equation (x - x1)(x - x2) + (y - y1)(y - y2) = 0.

A chord joins two points of a circle. A secant is a line that cuts the circle at two points. A tangent touches the circle at exactly one point and is perpendicular to the radius drawn to that point.

To see how a line meets a circle, compare the perpendicular distance d from the centre to the line with the radius r. If d is greater than r the line misses the circle. If d equals r the line is a tangent. If d is less than r the line cuts the circle in two points and forms a chord.

The tangent to x^2 + y^2 = a^2 at the point (x1, y1) on it is x x1 + y y1 = a^2. The line y = mx + c touches the circle x^2 + y^2 = a^2 when c^2 = a^2 (1 + m^2).

The length of the tangent drawn from an outside point (x1, y1) to the circle x^2 + y^2 + 2gx + 2fy + c = 0 is the square root of (x1^2 + y1^2 + 2g x1 + 2f y1 + c).

## The parabola

A parabola is the set of points in a plane that are equally far from a fixed point, the focus, and a fixed line, the directrix. Its eccentricity is e = 1.

The standard parabola y^2 = 4ax, with a positive, opens to the right. Its vertex is the origin, its focus is (a, 0), its directrix is the line x = -a, and its axis is the x-axis. The length of its latus rectum, the chord through the focus perpendicular to the axis, is 4a.

The other three standard forms are y^2 = -4ax, which opens left with focus (-a, 0) and directrix x = a; x^2 = 4ay, which opens upward with focus (0, a) and directrix y = -a; and x^2 = -4ay, which opens downward with focus (0, -a) and directrix y = a.

The parabola x^2 = 4y has a = 1, so its focus is (0, 1) and its directrix is y = -1. Written as a function it is y = x^2 / 4.

The graph of y = ax^2 + bx + c is a parabola with a vertical axis. It opens upward when a is positive and downward when a is negative, and its vertex is at x = -b / (2a).

Parabolic shapes are used in satellite dishes, torch and headlight reflectors, and the cables of suspension bridges. Rays parallel to the axis reflect through the focus, and light from a source at the focus leaves as a parallel beam. A ball thrown through the air follows a parabola when air resistance is ignored.

## The ellipse

An ellipse is the set of points in a plane for which the sum of the distances to two fixed points, the foci, is constant. That constant sum equals the length of the major axis, 2a. Its eccentricity is between 0 and 1.

The standard ellipse x^2 / a^2 + y^2 / b^2 = 1, with a greater than b, has its centre at the origin and its major axis along the x-axis. The major axis has length 2a and the minor axis has length 2b. The vertices are (a, 0) and (-a, 0).

For this ellipse, c^2 = a^2 - b^2 and the foci are (c, 0) and (-c, 0). The eccentricity is e = c / a, so the foci are at (ae, 0) and (-ae, 0), and the directrices are the lines x = a / e and x = -a / e. The latus rectum has length 2 b^2 / a.

The ellipse x^2 / 16 + y^2 / 4 = 1 has a = 4 and b = 2. Then c^2 = 16 - 4 = 12, so the foci are at plus and minus the square root of 12, about 3.46, on the x-axis, and the eccentricity is about 0.87.

When a equals b the ellipse becomes a circle and the two foci join at the centre, so the eccentricity of a circle is 0. If b is greater than a, the major axis is along the y-axis and the foci are on the y-axis.

The planets move around the Sun in elliptical orbits with the Sun at one focus.

## The hyperbola

A hyperbola is the set of points in a plane for which the difference of the distances to two fixed points, the foci, is constant and equal to 2a. It has two separate branches and its eccentricity is greater than 1.

The standard hyperbola x^2 / a^2 - y^2 / b^2 = 1 has its centre at the origin and its transverse axis along the x-axis. Here c^2 = a^2 + b^2, the foci are (c, 0) and (-c, 0), the vertices are (a, 0) and (-a, 0), and the eccentricity is e = c / a. The latus rectum has length 2 b^2 / a.

The branches approach the two asymptotes y = (b / a) x and y = -(b / a) x without ever touching them. When a equals b the hyperbola is called rectangular. The graph of xy = c, or y = k / x, is a rectangular hyperbola with the coordinate axes as its asymptotes.

## Conic sections

The circle, ellipse, parabola and hyperbola are called conic sections because each is made by cutting a double cone with a plane. A cut perpendicular to the axis gives a circle. A tilted cut that goes through one nappe gives an ellipse. A cut parallel to the slant side gives a parabola. A steeper cut through both nappes gives a hyperbola.

Every conic is the set of points whose distance from a focus is e times its distance from the matching directrix, where e is the eccentricity. For a circle e = 0, for an ellipse 0 < e < 1, for a parabola e = 1, and for a hyperbola e > 1.

The general second-degree equation A x^2 + B xy + C y^2 + D x + E y + F = 0 represents a conic. The sign of B^2 - 4AC tells which one: negative gives an ellipse (a circle if A = C and B = 0), zero gives a parabola, and positive gives a hyperbola, apart from degenerate cases such as a pair of lines.

## Worked examples

For the points A(1, 2) and B(7, 10): the distance AB is the square root of (6^2 + 8^2) = 10, the midpoint is (4, 6), and the slope is 8 / 6 = 4/3.

The line through (0, 1) and (2, 5) has slope (5 - 1) / (2 - 0) = 2 and y-intercept 1, so its equation is y = 2x + 1.

The line perpendicular to y = 2x + 1 has slope -1/2. The line y = -0.5x + 2 is one such line, and the line y = 2x - 3 is parallel to y = 2x + 1.

The circle with centre at the origin and radius 5 is x^2 + y^2 = 25.

## Common mistakes in coordinate geometry

Writing the coordinates in the wrong order: x always comes first and y second.

Forgetting that a vertical line has no slope, and dividing by zero in the slope formula.

Using the sum instead of the difference in the distance formula, or forgetting to take the square root.

Mixing up the signs in the circle equation: the circle (x - 2)^2 + (y + 1)^2 = 9 has centre (2, -1), not (-2, 1).

Thinking that perpendicular lines have slopes that are only opposite in sign: the product of the slopes must be -1, so the slopes are negative reciprocals.
