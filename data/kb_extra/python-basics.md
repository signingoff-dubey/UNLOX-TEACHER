# Python basics

## What Python is and how it runs

Python is a high-level, general-purpose programming language known for code that reads almost like English. It is used for websites, data analysis, automation, science and teaching. These notes describe Python 3.

Python is an interpreted language. You write instructions in a file that ends in .py, and the Python interpreter reads and runs them one line at a time, from the top to the bottom. You can also type single lines into the interactive prompt, also called the REPL.

The built-in print function shows values on the screen. The call print("Hello, world!") displays Hello, world! Text, called a string, goes inside quotes. Numbers need no quotes, and print(2 + 3) displays 5.

A comment starts with the # sign. Python ignores everything after it on that line, so comments are notes for people who read the code.

## Variables and assignment

A variable is a name that refers to a value stored in the computer's memory. The equals sign = is the assignment operator: it stores the value on its right under the name on its left. After age = 15, the name age refers to the whole number 15.

Python is dynamically typed, so you do not declare the type of a variable. The same name can later be assigned a value of another type. The type belongs to the value, and the function type() tells you what it is.

Variable names may contain letters, digits and underscores, and they cannot start with a digit or contain spaces. Names are case sensitive, so name and Name are different variables. The convention is lowercase words joined by underscores, called snake case, such as total_price. Reserved words such as if, for, while, def and class cannot be used as names.

Several variables can be assigned at once: x, y = 3, 4 gives x the value 3 and y the value 4. Writing x = y = 0 gives both names the value 0.

## Data types

The main built-in types are int for whole numbers such as 15, float for decimal numbers such as 1.55, str for text such as "Asha", and bool for the two truth values True and False. The special value None means no value.

Python integers can be as large as memory allows. A float is an approximation, so 0.1 + 0.2 gives 0.30000000000000004 and not exactly 0.3.

Type conversion changes a value from one type to another: int("42") gives the number 42, str(42) gives the text "42", and float("1.5") gives 1.5. The input() function always returns a string, so convert it with int() or float() before doing arithmetic: age = int(input("Age? ")).

## Operators and arithmetic

The arithmetic operators are + for addition, - for subtraction, * for multiplication, / for division, // for floor division, % for the remainder and ** for powers. The division 7 / 2 gives 3.5, the floor division 7 // 2 gives 3, the remainder 7 % 2 gives 1, and 2 ** 3 gives 8.

Python follows the usual order of operations: brackets first, then powers, then multiplication and division, then addition and subtraction. So 2 + 3 * 4 is 14, while (2 + 3) * 4 is 20.

The comparison operators are == for equal, != for not equal, <, >, <= and >=. They give True or False. The logical operators and, or and not combine conditions.

A single equals sign = assigns a value, while a double equals sign == compares two values. Writing = where == is needed is one of the most common beginner mistakes.

## Strings

A string is a sequence of characters written in single or double quotes. The + operator joins strings, so "Hi " + "Ravi" gives "Hi Ravi", and * repeats them, so "ab" * 3 gives "ababab". Joining a string and a number with + causes a TypeError, so convert the number with str() first.

An f-string puts values straight into text. Put an f before the opening quote and write expressions in curly brackets: with total = 120, f"Total: {total}" gives Total: 120.

Characters are numbered from 0, so for s = "Python" the value s[0] is "P" and s[-1] is "n". A slice such as s[0:3] gives "Pyt": it includes the start index and excludes the end index. The function len(s) gives the number of characters, 6.

Useful string methods are upper(), lower(), strip() to remove surrounding spaces, replace(old, new), and split() to cut a string into a list of words.

## Making decisions with if

An if statement runs a block of code only when its condition is True. The block comes after a colon and must be indented, normally by four spaces. Python uses indentation, not curly brackets, to show which lines belong together.

With marks = 72, the code if marks >= 40: print("Pass") else: print("Try again") prints Pass, because 72 is at least 40 and so the else part is skipped. The keyword elif adds further conditions between if and else, and only the first block whose condition is True runs.

Every line that opens a block, such as if, else, for, while and def, must end with a colon. Forgetting the colon causes a SyntaxError, and wrong indentation causes an IndentationError.

## Loops

A for loop repeats a block once for each item in a sequence. The function range(n) produces the numbers 0 up to n - 1, so for i in range(3) runs 3 times with i equal to 0, 1 and 2. The call range(1, 4) produces 1, 2 and 3, because the end number is never included, and range(0, 10, 2) counts in steps of 2.

A for loop can also walk through a list: for fruit in fruits: print(fruit) shows every item in turn.

A while loop repeats as long as its condition stays True. With count = 2 and the body print(count) followed by count = count - 1, the loop while count > 0 prints 2 and then 1 and stops when count reaches 0. Something inside a while loop must change the condition, otherwise the loop never ends and the program is stuck in an infinite loop.

The keyword break leaves a loop immediately, and continue skips to the next round. Loops can be placed inside loops, which is called nesting.

Use a for loop when the number of repeats is known or when walking through a collection, and a while loop when you repeat until something changes.

## Lists, tuples and dictionaries

A list holds many values in order, written in square brackets: fruits = ["apple", "mango", "kiwi"]. Lists are mutable, which means they can be changed. Counting starts at 0, so fruits[0] is "apple" and fruits[-1] is the last item. The method append adds an item at the end, so after fruits.append("grape") the call len(fruits) gives 4.

Other list methods are insert(i, x) to add at a position, remove(x) to delete a value, pop() to take off the last item, and sort() to order the list. The expression "kiwi" in fruits is True when the item is present.

A tuple is like a list but immutable, written in round brackets: point = (3, 4). A set keeps only unique values, written in curly brackets.

A dictionary stores pairs of keys and values: student = {"name": "Asha", "age": 15}. The value is found by its key, so student["name"] gives "Asha", and student["city"] = "Pune" adds a new pair. The method get returns None instead of an error when a key is missing, and items() lets a loop walk through all pairs.

## Functions

A function is a named block of code that you can run again whenever you need it. It is defined with the keyword def, then a name, brackets with the inputs, called parameters, and a colon. The indented lines below it are the body.

def greet(name): return "Hi " + name defines a function with one parameter. Calling greet("Ravi") runs the body with name set to "Ravi" and gives back "Hi Ravi". The keyword return sends a result back to the caller, and a function without return gives back None.

A parameter can have a default value, as in def power(x, n=2). Variables created inside a function are local and cannot be used outside it.

Print shows a value on the screen, but return hands the value back so that the program can use it later. Functions let you write code once and use it often, give clear names to jobs, and avoid copy and paste errors.

## Common errors and mistakes

A SyntaxError means Python cannot understand the code, for example a missing colon or an unclosed bracket. An IndentationError means the indentation is wrong. A NameError means a name was used before it was created or was misspelled. A TypeError means an operation was used on the wrong type, such as "5" + 3. A ZeroDivisionError means a division by zero. An IndexError means a list position does not exist, and a ValueError means the value is of the right type but not acceptable, such as int("abc").

Read the error message from the bottom: the last line names the error and the lines above show where in the program it happened.

Beginners often make these mistakes: using = instead of == in a condition, forgetting the colon after if, for, while or def, mixing tabs and spaces or indenting inconsistently, expecting range(3) to include 3 (it gives 0, 1 and 2), forgetting that input() returns text, and writing a while loop that never changes its condition.

## Learning path

A Python program is built from a few pieces: variables to store values, operators to calculate, if and else to decide, loops to repeat, lists and dictionaries to hold many values, and functions to reuse code. Practise by changing small examples and running them again.
