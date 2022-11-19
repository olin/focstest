(*
- compiler.toploop for evaluating code (only available when running as bytecode form)
- lambdasoup package for parsing html
- probably need to redirect stdout/stderr? <https://stackoverflow.com/a/19528037> use w/ created pipe? or modify the Env.t returned by toplevel_env somehow
*)

let tests = [
  ("2 * 3", "- : int = 6")
  ; ({|failwith "Not Implemented"|}, {|Exception: Failure "Not Implemented".|})
  ; ("let f a = a * 2", "val f : int -> int = <fun>")
  ; ("f 3", "- : int = 6")
  ; ("f 4", "- : int = 7")
]

let test_selector = [
    "div.code pre"
  ; "pre code"
] |> String.concat ", "

let _tests_from_html h : string list =
  let open Soup in
    h |> parse
    |> select test_selector
    |> to_list
    |> List.filter_map leaf_text

let eval_expression expr =
  let did_succeed = Toploop.use_input Format.str_formatter (Toploop.String expr) in
  let output = Format.flush_str_formatter () in
  (did_succeed, output)

let run_test (input, expected) =
  let _, output = eval_expression input in

  let did_pass = String.compare (String.trim output) (String.trim expected) = 0 in

  Printf.printf "Test %s:\nInput:\t%s\nWant:\t%s\nGot:\t%s\n"
    (if did_pass then "passed" else "failed") input expected output

let () =
  Toploop.initialize_toplevel_env ();

  tests
  |> List.iter run_test
;;
