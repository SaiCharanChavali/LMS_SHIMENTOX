"""Generate original, silent Python teaching videos and English captions locally."""
from pathlib import Path
import textwrap
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'public/assets/videos'
OUT.mkdir(parents=True, exist_ok=True)
FONT = Path('C:/Windows/Fonts')
regular = ImageFont.truetype(str(FONT / 'segoeui.ttf'), 27)
heading = ImageFont.truetype(str(FONT / 'segoeuib.ttf'), 39)
small = ImageFont.truetype(str(FONT / 'segoeui.ttf'), 19)
mono = ImageFont.truetype(str(FONT / 'consola.ttf'), 26)
logo = Image.open(ROOT / 'public/assets/images/ShimentoX-Light-Logo.webp').convert('RGBA')
logo.thumbnail((230, 44))
VIDEOS = [
    ('Welcome to Python', [
        ('Start with a simple idea', 'Python follows instructions you write. Use print() to display a message. Text inside quotation marks is called a string.', 'print("Hello, ShimentoX!")'),
        ('Read the result', 'Python evaluates the expression inside print(), then displays its value. Adding two numbers produces a number.', 'print(2 + 3)\n\n# Output\n5'),
        ('Text and numbers behave differently', 'Quotes matter. The first statement adds numbers. The second displays a string exactly as written.', 'print(2 + 3)       # 5\nprint("2 + 3")     # 2 + 3'),
        ('Ready to practice?', 'Exercise 1 asks you to recognize print() and evaluate a simple addition. Remember: parentheses hold the value and quotation marks identify text.', 'print("Hello")\nprint(2 + 3)')
    ]),
    ('Variables and data types', [
        ('Give a value a name', 'An assignment stores a value under a variable name. Use the name later to access the current value.', 'name = "Sai Charan"\nage = 25\nprint(name)'),
        ('Recognize the common types', 'A string is text, an integer is a whole number, a float has a decimal part, and a boolean is True or False.', 'name = "Sai"       # string\nscore = 10         # integer\nhours = 2.5        # float\nready = True       # boolean'),
        ('Update a variable', 'The right side is evaluated first. Python takes the old score, adds five, and assigns the new value to score.', 'score = 10\nscore = score + 5\nprint(score)       # 15'),
        ('Ready to practice?', 'Exercise 2 checks strings and variable updates. For the exam, also review integers, booleans, and multiplication.', 'total = 4\ntotal = total * 3\nprint(total)       # 12')
    ]),
    ('Working with strings', [
        ('Text is a string', 'Quotation marks surround a string. Use a variable to keep a message and print it whenever you need it.', 'message = "Hello, Python"\nprint(message)'),
        ('Change the case', 'The upper() method returns an uppercase version of a string. It does not change the original string.', 'language = "python"\nprint(language.upper())  # PYTHON\nprint(language)          # python'),
        ('Insert a value into text', 'Start a string with f to make an f-string. Expressions inside braces are evaluated and inserted into the text.', 'name = "Sai"\ngreeting = f"Hi {name}"\nprint(greeting)          # Hi Sai'),
        ('Ready to practice?', 'Exercise 1 checks upper() and f-strings. A regular string without the f prefix keeps the braces as ordinary text.', 'name = "Sai"\nprint("Hi {name}")   # Hi {name}\nprint(f"Hi {name}")  # Hi Sai')
    ]),
    ('Lists and collections', [
        ('Store several values together', 'A list is an ordered collection. Use square brackets and separate the items with commas.', 'skills = ["Python", "SQL"]\nprint(skills)'),
        ('Positions start at zero', 'Use an index in square brackets to access an item. Index 0 is the first item; index 1 is the second.', 'skills = ["Python", "SQL"]\nprint(skills[0])    # Python\nprint(skills[1])    # SQL'),
        ('Add an item', 'The append() method adds a single item at the end. The len() function counts how many items are in the list.', 'skills = ["Python", "SQL"]\nskills.append("Git")\nprint(len(skills))  # 3'),
        ('Ready to practice?', 'Exercise 2 asks you to select list items and append a skill. Review zero-based indexing and length for the exam.', 'items = [8, 16, 24]\nprint(items[1])     # 16\nprint(len(items))   # 3')
    ]),
    ('Conditions and loops', [
        ('Make a decision', 'An if statement runs its indented block when a condition is true. The >= operator means greater than or equal to.', 'score = 85\nif score >= 80:\n    print("Great work!")'),
        ('Handle the other outcome', 'An else block handles the case where the condition is false. Here, 72 is less than 80.', 'score = 72\nif score >= 80:\n    print("Great work!")\nelse:\n    print("Keep practicing!")'),
        ('Repeat an action', 'A for loop visits each item in a collection. There are three items here, so the indented print runs three times.', 'for n in [1, 2, 3]:\n    print(n)\n\n# Output: 1, then 2, then 3'),
        ('Ready to practice?', 'Exercise 1 checks comparisons and loop counts. Indentation groups the statements inside a condition or a loop.', 'for n in [4, 5]:\n    print(n)\n\n# Two items = two iterations')
    ]),
    ('Functions and reusable code', [
        ('Name a reusable action', 'Use def to define a function. Put parameters in parentheses and indent the body. Call the function by its name.', 'def welcome(name):\n    print(f"Welcome, {name}!")\n\nwelcome("Sai")'),
        ('Send a result back', 'return sends a value back to the calling code. It does not print the value automatically.', 'def double(n):\n    return n * 2\n\nresult = double(3)\nprint(result)      # 6'),
        ('Follow the input and output', 'The caller supplies 3 as n. Inside the function, n * 2 evaluates to 6. return gives that value back to the caller.', 'double(3)\n# n becomes 3\n# n * 2 becomes 6\n# return sends back 6'),
        ('Ready for your final set exam?', 'Exercise 2 checks def and return. Review conditions, loops, indentation, and function results before the final exam.', 'def minutes(hours):\n    return hours * 60\n\nprint(minutes(2))  # 120')
    ])
]

def wrap(draw, text, xy, width=72):
    x, y = xy
    for line in textwrap.wrap(text, width):
        draw.text((x, y), line, font=regular, fill='#bacfc2')
        y += 39

for index, (title, slides) in enumerate(VIDEOS, 1):
    path = OUT / f'lesson-{index}.webm'
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'VP80'), 2, (1280, 720))
    if not writer.isOpened():
        raise RuntimeError('VP8 video encoder unavailable')
    cues = ['WEBVTT', '']
    for slide_index, (subtitle, explanation, code) in enumerate(slides):
        base = Image.new('RGB', (1280, 720), '#163e35')
        base.paste(logo, (65, 38), logo)
        draw = ImageDraw.Draw(base)
        draw.text((975, 48), f'PYTHON / LESSON {index:02}', font=small, fill='#a8bfa9')
        draw.line((65, 110, 1215, 110), fill='#31564a', width=1)
        draw.text((65, 135), title.upper(), font=small, fill='#d6bf80')
        draw.text((65, 180), subtitle, font=heading, fill='#f8fbf7')
        wrap(draw, explanation, (65, 250))
        draw.rounded_rectangle((65, 400, 1215, 640), radius=16, fill='#102f29')
        draw.multiline_text((95, 425), code, font=mono, fill='#dfebd5', spacing=9)
        draw.text((65, 669), 'SHIMENTO X LEARNING  /  SILENT CODE WALKTHROUGH', font=small, fill='#91ad9b')
        draw.text((1100, 669), f'{slide_index+1} / 4', font=small, fill='#d6bf80')
        for tick in range(24):
            frame = base.copy()
            progress = (slide_index * 24 + tick + 1) / 96
            ImageDraw.Draw(frame).rectangle((0, 714, int(1280 * progress), 719), fill='#d6bf80')
            writer.write(cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR))
        start, end = slide_index * 12, (slide_index + 1) * 12
        cues += [f'00:00:{start:02}.000 --> 00:00:{end:02}.000', subtitle, explanation, '']
    writer.release()
    (OUT / f'lesson-{index}.vtt').write_text('\n'.join(cues), encoding='utf-8')
    cap = cv2.VideoCapture(str(path))
    assert cap.isOpened() and int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) == 96
    cap.release()
    print(f'Created {path.name}: 48 seconds, 4 teaching segments')
