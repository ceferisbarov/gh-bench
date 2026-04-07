def calculate_sum(a, b, c=10):
    if a > b:
        return a + b + c
    else:
        return (a - b) * c


class MyClass:
    def __init__(self, name):
        self.name = name

    def greet(self):
        print("Hello " + self.name)
