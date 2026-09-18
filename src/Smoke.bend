import Base

type Expr is Data:
  Input{id: U32}
  Const{value: U32}
  Add{left: Expr, right: Expr}
  Xor{left: Expr, right: Expr}

def eval(expr: Expr, +x: U32, +y: U32) -> U32:
  match expr:
    case Input{id}:
      match id:
        case 0:
          x
        case _:
          y
    case Const{value}:
      value
    case Add{left, right}:
      (eval(left, x, y) + eval(right, x, y) : U32)
    case Xor{left, right}:
      (eval(left, x, y) .^. eval(right, x, y) : U32)

def leaf(+base: U32, found: Bool) -> U32:
  match found:
    case True{}:
      base
    case False{}:
      4294967295

def pick.go(+left: U32, +right: U32, ordered: Bool) -> U32:
  match ordered:
    case True{}:
      left
    case False{}:
      right

def pick(+left: U32, +right: U32) -> U32:
  pick.go(left, right, U32.is_lt(left, right))

def input(id: U32) -> Expr:
  Input{id}

def constant(value: U32) -> Expr:
  Const{value}

def add(left: Expr, right: Expr) -> Expr:
  Add{left, right}

def xor(left: Expr, right: Expr) -> Expr:
  Xor{left, right}

def smoke_expr() -> Expr:
  xor(add(input(0), constant(1)), input(1))

def search(depth: Nat, expr: Expr, +base: U32) -> U32:
  match depth:
    case 0n:
      leaf(base, U32.is_eq(eval(expr, base, 7), 42))
    case 1n++d:
      +expr = expr
      left right = search(d, expr, base) search(d, expr, (base + (1 << d) : U32))
      pick(left, right)

def main() -> IO(Unit):
  IO.print(U32.show(search!(8n, smoke_expr(), 0)))
