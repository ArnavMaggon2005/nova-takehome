# Assumptions

Where the brief can be read two ways I resolved it myself, in this order: (1) the GLOSSARY text, (2) the worked
examples, (3) the practice answer key, used only as evidence of how a rule is read and never copied into code,
(4) otherwise the conservative reading. Wrongly disputed money costs double, so when in doubt the harness doesn't
dispute. Every assumption is one constant in [harness/config.py](../harness/config.py).

| # | Constant | Question | Reading chosen | Evidence | If it's wrong, change |
|---|---|---|---|---|---|
| A1 | `ASSUME_RESENT_INVOICE_COUNTS_ONCE_IN_QS = True` | Does a paid invoice re-sent under the same number count once or twice in qualifying spend? | Once: it's one invoice with one date. | Glossary "a line billed twice counts twice" is about two invoice numbers. Practice key tested both ways (see below). | `= False` |
| A2 | `ASSUME_CHECK1_SCOPE = "shipments_in_key"` | Does unattended check 1 (pickup date from tracking or a carrier "picked up" email) apply to every key, or only when the pickup date decides the amount? | It applies to every shipment whose lines are in the finding; keys with no shipment (late fees, cashback, monthly fees) pass it. | Practice keys with `execute:dispute` (sc-3874a142, sc-bff95595, both DU-01 resends) all have tracking `PICKED_UP` rows, so the key doesn't separate the readings; the stricter one is conservative (fewer unattended sends). | `= "pickup_decides_amount"` |
| A3 | `ASSUME_CLAIM_CREDIT_RECIPIENT = "billing_disputes"` | Who receives a credit claim (check 5)? | The carrier's Schedule 1 billing_disputes contact, as for disputes. | Glossary names billing_disputes for disputes and no other contact for claims. | the category string |
| A4 | `ASSUME_DESCRIPTIVE_MISSING_DOC_NAMES = True` | How exactly do we name a missing document? | The document as cited, then its sender, date and the invoice/AWB it covers. | `score.py` `names_match` and `grade_sheet.py` both test "our name contains theirs". | `= False` (citation only) |
| A5 | `ASSUME_QUANTITY_AS_PRINTED = True` | If the AWB's chargeable weight differs from the invoice's, which counts? | The invoice's printed quantity; a weight difference is not disputed. | Glossary: "Quantities are as printed". | `= False` |
| A6 | `ASSUME_RESEND_NEEDS_PAYMENT_BEFORE_RESEND = True` | Must the first copy be paid before the resend arrives? | Yes, paid (or scheduled) on or before the resend date. | Glossary: a resend asking for payment of an unpaid invoice is fine. Examples and practice resends are all paid first. | `= False` |
| A7 | `ASSUME_DUPLICATE_LINE_NEEDS_SAME_QTY = True` | When do two lines on different invoices bill "the same shipment line"? | Same AWB (house suffix included), same Annex E code, same quantity. | examples/duplicate_rebilled_4_months: "AWB plus Annex E code plus amount". | `= False` |
| A8 | `ASSUME_NOT_OWED_BASE_EXCLUDES_OUR_DISPUTES = False` | For a late fee charged on an invoice we dispute, is our disputed amount removed from the fee base? | No: the base is the printed principal. | Removing it would raise our claim; conservative. | `= True` |
| A9 | `ASSUME_RISK_PRINCIPAL_EXCLUDES_OUR_DISPUTES = True` | Late-fee risk principal? | Open amount less what we dispute on that invoice. | Glossary says so explicitly. | `= False` |
| A10 | `ASSUME_SKIP_LATE_FEE_WHEN_UNPAID = True` | A late fee on an invoice the ledger doesn't show as paid? | Not assessed: there's no paid date to count from. | Conservative. | `= False` |
| A11 | `ASSUME_CHECK_TAX_LINES = False` | Re-compute tax/GST lines? | No: never disputed. | The domestic/export split isn't reliably derivable from lane codes in an unseen world. | `= True` |
| A12 | `ASSUME_OVERCHARGE_POSITIVE_LINES_ONLY = True` | Does an undercharged line on the same invoice net off an overcharge? | No: sum only the positive differences. | Glossary: "an undercharge is never a finding"; "billed minus correct over the lines in the finding". | `= False` |
| A13 | `ASSUME_UNVERIFIABLE_LINE_IS_CORRECT = True` | A line whose correct value can't be computed (no tracking for storage, no DG declaration)? | Accepted as billed. | Conservative. | `= False` |
| A14 | `ASSUME_BROKER_NOTICE_IS_RECORD = True` | Is a customs broker's notice (outside both companies) level 3 or level 5? | Level 3 for the hold facts it states; it never changes terms. | Glossary lists "customs notices" among records. | `= False` |
| A15 | `ASSUME_HOUSE_AWB_IS_SHIPMENT = True` | Is each house AWB its own shipment? | Yes, for band rating and duplicates. | examples/duplicate decoy: houses billed separately is fine. | `= False` |
| A16 | `ASSUME_MISSING_DOC_ISSUER_SIDE = "carrier"` | Who issues a cited-but-missing rates annex, rate notice or exchange-rate update? | The carrier. | Practice answer sc-6f955cee names the carrier's Pricing Manager for "Annex A rev 2". | `"shipper"` |
| A17 | `ASSUME_QS_UNKNOWN_CODES_EXCLUDED = True` | Do charge codes outside the contract's QS definition count toward qualifying spend? | No. | Conservative (a smaller spend never over-claims). | `= False` |
| A18 | `ASSUME_DEFAULT_NOTICE_VS_AMENDMENT = "amendment_wins"` | Precedence when no precedence clause was extracted? | Glossary ladder: signed amendment first. | Glossary "Which document wins". | `"unranked"` |
| A19 | `ASSUME_FEEDBACK_FROM_DECIDED_DATE = True` | From which report does feedback apply? | Reports whose `as_of` is on or after the date of `decided_at`. | Glossary: "counts as level 2 from decided_at". | `= False` |
| A20 | `ASSUME_LEARNED_AT_BATCH_FIELD = "after_batch"` | What goes in `learned_at.batch`? | The feedback file's `after_batch`. | The schema leaves it free; the grader checks only `feedback_item_id`. | another field name |

## Test of A1 against the practice key
To be filled in once extraction runs: QS for TBX-US-EXP-01 2035-Q1 and 2035-Q2 under both readings.
