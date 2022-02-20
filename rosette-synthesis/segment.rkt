#lang rosette/safe

(require rosette/lib/synthax)
(current-bitwidth #f)

; --------
; activity 8
; this is a pretty artificial scenario, but it lets us start playing with
; control flow (e.g., conditionals)
; so let's try it out!

; Scenario: We've segmented a bunch of PDFs into individual text elements.
; A user is trying to turn the PDFs into structured data, and one of their
; tasks is to identify which text elements represent titles.
; They've labeled a few elements as titles or not tiles.  Text elements
; are also labeled with their font size and the number of words inside.
; The goal of this assignment is to learn a program to apply to the
; remaining texts in the user's corpus to categorize them as titles or
; not titles.
;
; This is a sample (below), but feel free to play around with more realistic
; scenarios. :)
(define texts
  [list (list 20 450 #f) (list 30 1200 #f) (list 70 4 #t) (list 72 9 #t) (list 9 4 #f) (list 72 200 #f)])

(define (get-font-size t)
  (list-ref t 0))

(define (get-num-words t)
  (list-ref t 1))

(define (get-is-title t)
  (list-ref t 2))

; the next three lines are just to help you understand what these getters are doing
(get-font-size (list-ref texts 0))
(get-num-words (list-ref texts 0))
(get-is-title (list-ref texts 0))

; Now write a synthesizer that can learn a program for labeling texts as titles
; or not titles based on the examples in our texts list.

; Hint: if you end up using the #:forall (list i) approach in your solution,
; remember that i can be less than 0 and greater than the length of the texts
; list.

; Our synthesized program will have the following type signature:
; (categorize integer? integer?) → boolean?
;
; Concretely, categorize should take <font-size> and <num-words> as arguments and return <is-title>.

; Define a grammar. Our grammar allows < > comparison in addition to AND connectives.
(define-synthax (expr font-size num-words depth)
  (assert (>= depth 0))
  (choose
   font-size
   num-words
   (??)
   ((choose < >) (expr font-size num-words (sub1 depth)) (expr font-size num-words (sub1 depth)))
   (and (expr font-size num-words (sub1 depth)) (expr font-size num-words (sub1 depth))) ))

; Sketch of the program we want to synthesize.
(define (categorize font-size num-words)
  (expr font-size num-words 2))

; Verification condition.
(define (check impl font-size num-words is-title)
  (assert (equal? (impl font-size num-words) is-title)))

; Check that the synthesized program satisfies all I/O examples.
; Bound i in the VC to not extend beyond the length of texts.
(define-symbolic i integer?)
(assume (>= i 0))
(assume (< i (length texts)))

; Synthesize a solution from I/O examples.
(define solution
  (synthesize
   #:forall (list i)
   #:guarantee (assert(check categorize (get-font-size (list-ref texts i)) (get-num-words (list-ref texts i)) (get-is-title (list-ref texts i)) ))))

(if (sat? solution) (print-forms solution) (print "UNSAT"))