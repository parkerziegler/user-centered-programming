b = 1
c = 2
d = 3
a = d
if a:
    d = b + d
    c = b + d
else:
    b = b + 1
    d = b + 1
a = b + c
print(a)
