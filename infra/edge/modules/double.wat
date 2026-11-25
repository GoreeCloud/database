;; First-party no-WASI pure function for disposable Wasmtime preview.
(module
  (func (export "run") (param i32) (result i32)
    local.get 0
    i32.const 2
    i32.mul)
)
