## Make dimensions and units explicit
A rectangle's area is width times height, its perimeter is twice their sum and its diagonal follows the Pythagorean theorem. If lengths are centimetres, area is square centimetres. A correct number with an incorrect unit is still an incorrect report.

Require positive dimensions at the boundary. The workshop supplies positive inputs, allowing its helper to focus on fitting. A reusable public class should also document numeric types and reject nonfinite values when they would make calculations meaningless.

## Whole fits differ from area ratios
For a regular axis-aligned grid without rotation, multiply the whole number fitting across the width by the whole number fitting down the height. Unused strips cannot automatically combine into another complete rectangle.

A 9 by 5 rectangle has area 45. A 2 by 2 rectangle has area 4, but eleven such rectangles do not fit in this grid. Four fit across and two fit down, giving eight. Leftover dimensions explain why dividing areas overestimates the result.

## Worked example: geometry with a stated fitting rule
```
from math import hypot

class Rectangle:
    def __init__(self, width, height):
        if width <= 0 or height <= 0:
            raise ValueError("Positive dimensions required")
        self.width = width
        self.height = height

    def area(self):
        return self.width * self.height

    def perimeter(self):
        return 2 * (self.width + self.height)

    def diagonal(self):
        return hypot(self.width, self.height)

    def grid_fit(self, sw, sh):
        if sw <= 0 or sh <= 0:
            raise ValueError("Positive small dimensions required")
        return int(self.width // sw) * int(self.height // sh)

room = Rectangle(9, 5)
print(room.area())
print(room.perimeter())
print(room.grid_fit(2, 2))
```

The output is 45, 28 and 8. Floor division counts whole placements per direction. This example assumes finite numeric dimensions and does not solve arbitrary packing with rotated or mixed orientations.

## Preserve the square invariant
A square requires equal width and height. Inheriting independent dimension setters can let callers turn it into a non-square. Override every relevant mutation or design a separate class with one side value. Sharing a small interface can be clearer than forcing inheritance.

An invariant must remain true after every public operation. Check it after construction and every setter. A class name does not itself guarantee correct state.

## Coding workshop and acceptance checks
Implement fits_inside for the stated no-rotation grid rule. Test equal-sized shapes, a smaller shape too large in one direction, the 9 by 5 example and leftover edge strips. Return a whole count.

Add perimeter and diagonal methods, comparing floating results with a tolerance. Add a square side setter and verify both dimensions remain equal after updates. Explain the distinction between area, grid fitting and general packing so users understand the project's guarantee.
