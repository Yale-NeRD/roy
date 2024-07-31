---
sidebar_position: 1
---

# Roy Tutorial

Let's get started with Roy and learn how to program with mutable remote objects!

Roy provides built-in classes for remote but _mutable_ object that can be used in Ray tasks. Currently, they are `RoyList`, `RoyDict`, and `RoySet`.

## Simple counter example

Let's take a look at a simple example of using `RoyDict` to count the frequency of words in a list.

```python
# Import RoyDict
from roy import RoyDict
```
