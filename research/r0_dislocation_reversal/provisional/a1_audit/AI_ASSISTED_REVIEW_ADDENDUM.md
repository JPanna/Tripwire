# A1 audit: AI-assisted, human-supervised review addendum (PROVISIONAL)

Status: reviewer-method amendment to `AUDIT_PROTOCOL.md` (v1.3, §3; secondary
reviewer substituted in v1.4), prepared 2026-10-11. **Owner-approved
2026-10-11** (§1). **No labelling has begun.**

## 1. Authorization and scope

- **Owner authorization (2026-10-11):** the owner expressly authorized
  switching the accepted A1 audit from independent human-only labelling to an
  explicitly documented AI-assisted, human-supervised hybrid, and preparing the
  isolated reviewer packages. The owner did **not** authorize assigning labels
  or starting any AI review run in that step.
- **Owner approval (2026-10-11):** the owner approved this AI-assisted hybrid
  audit with one modification. The secondary reviewer is **GPT-6 in a fresh,
  unpersonalized ChatGPT Temporary Chat**, replacing the previously planned
  Codex session. If GPT-6 is not available, the model actually selected is used
  and recorded. This substitution is a reviewer-method amendment, not a
  classifier revision. The primary Claude packet and all its hashes are
  unchanged.
- **Relation to earlier acceptance:** the independent (Codex) verdict "ACCEPT
  A1 v1.1 FOR BLINDED LABELING" evaluated the **human**-review protocol. This
  hybrid substitution is a later methodological change and is covered by that
  verdict only after its own documented approval.
- **Not a classifier revision:** this amendment does not touch the classifier
  and does not consume the single classifier-revision round
  (`AUDIT_PROTOCOL.md` §6).
- **Unchanged:** sampling and population definitions; the 865-market worksheet
  (SHA-256 `30b480ee1e93c4351a01767e7280b525319a2e04ceed8069818a49aadb3fae1a`);
  category tokens and slug patterns; the rubric's semantic rules
  (`LABELING_RUBRIC.md`, SHA-256
  `c938cc62e1b2258f04d7c0ca48d4c8b4755df7e5cf6a60b74be752b769830070`); all
  acceptance thresholds; the S4/S5 census gates; conservative UNRESOLVED
  scoring; the single-revision rule; the frozen preregistration.

## 2. Roles

| Role | Who | Sees | Does not see |
| --- | --- | --- | --- |
| Primary reviewer | a fresh, isolated Claude session | primary packet (all 865 rows: review id, category, slug) + rubric + prompt | repository; classifier or its predictions; key; strata; `category_refined`; earlier analyses; prices, trades, outcomes; web |
| Secondary reviewer | GPT-6 (or the model actually available, recorded from the interface) in a fresh, unpersonalized ChatGPT Temporary Chat | ONLY the blinded secondary CSV (assigned rows), the rubric and the isolated secondary prompt | all of the above, **plus** primary answers and why each row was selected; no Tripwire project context, repository, memory, custom instructions or plugins |
| Case-card drafter | a fresh, isolated session with no repository (any assistant) | one card's id, category, slug, both reviewers' answers and reasons, rubric | everything restricted above |
| Adjudicator | the human owner (not a crypto domain expert) | case cards | key, classifier, strata, `category_refined` until approved unblinding |
| Coordinator | Claude Code (this repository) | everything needed for packets, validation, records, later scoring | — (it must **not** draft domain explanations, because it has classifier and research context) |

**AI reviewers are labelling aids:** not human reviewers, not independent
human experts and not ground truth. The owner is not treated as a crypto
expert and is never asked to identify unfamiliar tokens, protocols, businesses
or people from memory.

## 3. Isolation requirements (checked before each run)

- A new session with no prior conversation, no project or repository access,
  no uploaded files other than the packet, and memory/personalisation off
  where the product allows.
- Web search, browsing, connectors and code tools disabled or unused. No
  market-page, price, result or outcome lookups during labelling or
  adjudication.
- A full repository session (e.g. a coding agent with the repo attached) is
  **not** an isolated reviewer environment.
- **Secondary session (ChatGPT):**
  - a new Temporary Chat, unpersonalized: no memory, no custom instructions,
    no project or Tripwire context, no plugins, apps or connectors, no web
    search or browsing, and no earlier reviewer answers;
  - uploads limited to the blinded secondary CSV and the rubric, plus the
    pasted secondary prompt;
  - the owner records the model selected in the model picker (GPT-6 if
    available) and confirms these settings in the interface at run time;
  - these product settings are as stated by the owner and were not verified
    by the coordinator.
- **Run record**, kept by the owner for every session:
  - product and model as displayed in its interface, and the version if shown;
  - date and time (UTC) of start and end;
  - isolation settings;
  - SHA-256 of the prompt and of each uploaded file;
  - SHA-256 of each returned output file.
  A model's self-description is not used as its identity.

## 4. Packets

**Primary packet** (`a1_primary_packet_v1`). Built deterministically from
committed files: the worksheet rows in order, split into 9 batches of 100
(last 65), keeping only `review_id, category, market_slug`. Delivered to the
owner as a downloadable archive and not committed (it can be rebuilt
identically).

| File | SHA-256 |
| --- | --- |
| `00_PRIMARY_REVIEW_PROMPT.md` | `811bcc209db6c173857eab970d1c4a9d74bbbfebabe0969b0bd9b55b546bc7f5` |
| `LABELING_RUBRIC.md` (byte-identical to the committed rubric) | `c938cc62e1b2258f04d7c0ca48d4c8b4755df7e5cf6a60b74be752b769830070` |
| `OUTPUT_TEMPLATE_primary_labels.csv` | `b87e458d1a621a34044bc79d1b74a186c40a85d7244553188daec301104381c7` |
| `batches/primary_batch_01.csv` (A1-0001..0100) | `4525171bbcfd8b98cf71cfc14b288cda14f5676981fa4c117cc98ff1428346c0` |
| `batches/primary_batch_02.csv` (A1-0101..0200) | `e09a35f381c451f19cdbe6c5189e91969a291642f7bb3e70cacc522b3cae5484` |
| `batches/primary_batch_03.csv` (A1-0201..0300) | `5aef3726c73cb4b12b3276756011781e9fda2642350b6c9bd9a29df68d4d8299` |
| `batches/primary_batch_04.csv` (A1-0301..0400) | `debbb5fa9d09348676f1195e0c3a045fc42bad6e8dab71f20cc83d86a0474910` |
| `batches/primary_batch_05.csv` (A1-0401..0500) | `4b599683bdf9a520bf746dd5900ec5d33f0bf3472014293c3111725f8b94208d` |
| `batches/primary_batch_06.csv` (A1-0501..0600) | `9b9aeabe758f627b0ef62b261548d06099d3583125e90dcbea1c9ebcd70dc58c` |
| `batches/primary_batch_07.csv` (A1-0601..0700) | `e91bdc9e749dcea86d43ab7a0b962721473854317477011357bbc9ee0029bd57` |
| `batches/primary_batch_08.csv` (A1-0701..0800) | `83ea522c626c70082f4362a3b1e179fdf0e995fd9efcdf05824463f1d271bb63` |
| `batches/primary_batch_09.csv` (A1-0801..0865) | `7a8f0b88090ba6070f664eaaa1a3f648d3a32f894600d38384caa01605468ac6` |

The packet was scanned for leakage. It contains no classifier rules,
predictions, stratum values, `category_refined` values, salts or earlier
findings. The rubric (unchanged) names these items only as things the reviewer
must not see, which discloses that a classifier and strata exist.

**Secondary packet:** built **only after** the primary output is finalized
(§6). It contains the original review ids, category and slug for: every row
the primary labelled UNRESOLVED on A or B, plus the 87-row QA sample (the first
87 ids in SHA-256(`a1-audit-v1-qa|review_id`) order). Rows are ordered by
SHA-256(`a1-audit-v1-secondary-order|review_id`), with no primary answers and
no selection reason. It also contains the same rubric and a secondary prompt
identical to the primary prompt except for its role line and file names.

## 5. Output schemas

All files are UTF-8 CSV with a header row and comma separator.

| File | Columns |
| --- | --- |
| `primary_labels.csv` (concatenation of the 9 batch outputs) | `review_id, A_crypto_related, B_crypto_price, reason` |
| `secondary_labels.csv` | `review_id, A_crypto_related, B_crypto_price, reason` |
| `adjudication_records.csv` | `review_id, category, market_slug, primary_A, primary_B, secondary_A, secondary_B, final_A, final_B, rubric_rule, context_note, disagreement_or_uncertainty, evidential_basis, escalated, owner_decision_reason, owner_approved_utc` |

Rules for the label files:
- A and B ∈ {YES, NO, UNRESOLVED}.
- B = YES only if A = YES. If A = NO, B = NO.
- `reason` is non-empty whenever A or B is UNRESOLVED.

Confidence statements or probabilities, if a model offers them, are kept out of
these files (at most as a separate, unscored note). They never substitute for
labels or for the fixed acceptance thresholds. Difficult cases are UNRESOLVED,
not guesses.

## 6. Import, validation and preservation (coordinator)

1. The owner returns each batch output file, plus the run record (§3).
2. The coordinator validates **mechanically**; a model's statement that it
   finished is not evidence:
   - header exactly as specified;
   - the set of review ids equals the batch's ids exactly: no missing, extra,
     duplicated or altered id, and the same order;
   - every label is valid, the B/A rule holds, and every UNRESOLVED has a
     reason;
   - the declared `ROWS` count matches.
3. A batch that fails validation is **not** hand-edited. Its output is kept
   with its SHA-256 as a failed attempt, and the whole batch is re-run in a new
   isolated session. Every attempt is logged.
4. After all 9 batches pass, they are concatenated in batch order into
   `primary_labels.csv`. Its SHA-256 and the batch hashes are recorded in an
   append-only run ledger. The file is then immutable: **primary review is
   finalized**, and only then is the secondary packet built.
5. The secondary output gets the same validation (ids equal the assigned set
   exactly), then hashing and immutability.
6. Populated label files are not committed until the blinding and access
   checks have been reviewed and the owner approves. The owner keeps
   downloaded copies, because the cloud container is ephemeral.

## 7. Adjudication without assumed crypto expertise

Every disagreement (primary ≠ secondary, on A or B) and every row left
UNRESOLVED by either reviewer gets one case card:

| Field | Content |
| --- | --- |
| Case | review id, category, market slug |
| Answers | primary A/B + reason; secondary A/B + reason (shown side by side, unlabelled as to which is "right") |
| Context | brief, neutral plain-English explanation of any named cryptocurrency, protocol, organization or person, drafted by an isolated case-card drafter (§2). Uncertain facts are marked uncertain; no lookups; no invented facts |
| Rubric rule | the specific `LABELING_RUBRIC.md` rule that applies |
| Issue | why the reviewers disagree or are uncertain |
| Proposed disposition | YES / NO / UNRESOLVED for A and B, with its evidential basis from the metadata and rubric only |
| Owner decision | final A/B (UNRESOLVED always available), written reason, approval time |

Further rules:
- The owner decides each case from the card. The owner is never asked to
  identify an unfamiliar asset from memory. When the card's evidence is
  insufficient, the owner keeps UNRESOLVED, which is then scored conservatively.
- Two models agreeing is **not** ground truth, and disputes are **not** settled
  by majority vote between models.
- A case needing specialist knowledge is escalated to a specialist under the
  same data-access and blinding restrictions, or stays UNRESOLVED.
- Rows where primary and secondary agree on definite labels are not
  re-adjudicated. Rows that were not sent to the secondary review keep the
  primary label (the adjudicated label for scoring), unless they are
  UNRESOLVED, which always go to adjudication.
- The owner approves the complete adjudication file (with its SHA-256) before
  the key is opened.

## 8. Methodological risks (disclosed)

- **Correlated AI errors.** Two language models may share training-data gaps
  or the same misreading of a token or slug. Agreement between them overstates
  reliability. The secondary review covers only the QA sample and UNRESOLVED
  rows, so a shared error on an unsampled row goes unseen.
  Mitigations: different products for primary and secondary; conservative
  scoring; human adjudication of every disagreement; reporting of the
  agreement rate; acceptance only via the unchanged gates.
- **Confident errors on obscure names.** Models may state wrong facts about
  small tokens or people. The prompt requires UNRESOLVED under uncertainty,
  case-card context marks uncertain facts, and no knowledge is fabricated.
- **Residual blinding leaks.** Categories are visible by design. The rubric
  names the existence of a classifier and strata. The secondary reviewer could
  partly infer that its rows include primary-UNRESOLVED items (it never learns
  which ones).
- **Coordinator context.** Claude Code knows the classifier and earlier
  findings. It is therefore limited to mechanical steps and does not draft
  domain explanations or proposed dispositions.
- **Owner as adjudicator** is a non-expert and also the study owner (a possible
  interest in acceptance). Mitigations: written reasons, UNRESOLVED always
  available, conservative scoring, approval before unblinding.

## 9. Primary prompt

The authoritative text is the part below the line in
`00_PRIMARY_REVIEW_PROMPT.md` (SHA-256 `811bcc20…bc7f5`, §4). It is pasted
unchanged into the isolated session, one batch per turn. The same wording is
reproduced here for the record; only the markdown quoting differs:

> You are the primary reviewer in a blinded labelling task. You label
> prediction-market metadata. You are an AI assistant, not a human expert, and
> your labels are review inputs, not ground truth.
>
> **Inputs.** Use ONLY the attached `LABELING_RUBRIC.md` (binding) and the
> attached batch CSV, which has the columns `review_id, category, market_slug`.
> Do not use web search, browsing, code execution against external sources, or
> any other tool or lookup. Do not look up the markets, their pages, prices,
> results or outcomes. You may use general knowledge of what a name means (for
> example, that a token or company is a crypto project). If that knowledge is
> uncertain, answer UNRESOLVED.
>
> **Task.** For EVERY row of the batch, answer two questions exactly as the
> rubric defines them:
> - `A_crypto_related`: is the market about cryptocurrencies or the crypto
>   ecosystem? YES, NO or UNRESOLVED.
> - `B_crypto_price`: is resolution specifically about a cryptocurrency price,
>   direction, market cap, FDV or dominance? YES, NO or UNRESOLVED.
>
> **Rules.**
> 1. Exactly one output row per input `review_id`, in the input order. Never
>    skip, merge, duplicate or invent review ids. Copy each id exactly.
> 2. Use only the uppercase values YES, NO, UNRESOLVED.
> 3. B = YES only if A = YES. If A = NO, B = NO. If A = UNRESOLVED, B is NO or
>    UNRESOLVED.
> 4. If the metadata does not establish an answer, use UNRESOLVED. Never guess.
> 5. `reason` is required whenever A or B is UNRESOLVED: one short sentence
>    saying what is missing or ambiguous. Otherwise it may be empty or a brief
>    rubric-based note. Do not put confidence scores or probabilities in the
>    label columns.
> 6. Do not comment on, rate or speculate about how these rows were chosen.
>
> **Output.** Return ONLY one CSV for this batch, in a single code block (or as
> a downloadable file named `primary_labels_batch_NN.csv`, with NN the batch
> number), with exactly this header:
>
> `review_id,A_crypto_related,B_crypto_price,reason`
>
> Quote any `reason` that contains a comma. After the CSV, write one line,
> `ROWS: <number of data rows>`, and nothing else. Your statement of completion
> is not accepted on its own: every row is checked mechanically.
