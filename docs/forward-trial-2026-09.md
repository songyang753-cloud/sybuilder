# Same-brief forward trial — limited evidence

Date: 2026-09-22. Two independent executions read either the original product-flow Skill
or this suite, then attempted `--only testcases` on the same synthetic file-upload brief.
They did not inspect each other's outputs or the preceding review findings. There was
no product implementation, platform authorization, network testing or paid-model call.
This is one qualitative trial per version, not a statistically controlled performance test.

## Observed outputs

| Check | Original | Suite |
|---|---|---|
| Local design cases | 25 | 26 |
| Known requirements with case references | 5/5 functional requirements | 5/5 functional requirements |
| Unspecified performance requirement | Explicitly not generated | Explicitly not generated |
| Open gaps | 12 | 11 |
| Product tests executed | 0 | 0 |
| Coverage process exit | 3, unresolved gaps and all cases unexecuted | 3, unresolved gaps and all cases unexecuted |
| Result claim | draft | draft |

The file-size boundary used 20 MiB = 20,971,520 bytes, with exact, minus-one and plus-one
cases in both outputs. Both covered the five-file limit, disguised non-PDF content,
collision choices, role restrictions, cancel/retry, offline recovery, refreshed visibility
and unauthorized direct links. Both avoided inventing a load window for the failure-rate
target. The extra suite case used a second disguised non-PDF format; the count difference
is not itself a quality improvement. Both included a manual sub-assertion trace table.

## Failure found and fixed

The suite's first project consistency check passed. After preserving actual stdout and its
gate receipt, the second check failed: it interpreted its own rule description as a product
freeze claim and its own diagnostic as a generated-file declaration. This was not a real
change to product status.

The correction strips only exact diagnostic blocks emitted by known project rules from
the text inspected for claims. It does not exclude log files, metadata directories or code
fences wholesale, and does not authenticate a transcript or treat its verdict as approval.
The original preserved trial files passed on recheck. The regression also adds an actual
freeze claim in the same transcript file and an unbacked generated artifact: both must fail.

## Still-open semantic issues

1. The testcases module forbids product-test execution, while its coverage completion
   condition rejects unexecuted cases. It can deliver honest local drafts, but its design
   completion and execution completion need separate explicit contracts before claiming
   independent module approval. Do not remove SKIPPED markers to obtain a green result.
2. Security guidance includes engineering baselines not stated in a PRD, whereas the case
   format only traces to FR/NFR and requires PRD-derived expectations. Both trials separated
   those baselines into a handoff and gaps rather than fabricating product requirements.
   A typed engineering-standard trace contract is still needed.
3. FR-level reference coverage does not prove coverage of every sub-assertion within a
   compound FR. Manual trace tables helped in this trial but are not a mechanical guarantee.
4. The standalone entry text and runtime-directory instructions need reconciliation;
   a local draft still uses minimal run metadata despite not running all ten stages.

These issues are not evidence that the suite lost those capabilities during packaging:
the first three were reported independently on both versions. They are nevertheless
release-quality work, not reasons to dismiss the findings as inherited problems.

## Claim boundary

This trial provides evidence that the tested design path retained its main safety behavior
and exposed a repeat-run defect. It cannot establish parity of research, PRD, design,
interactive deliverables, native document delivery, total latency, token cost or production
quality. Those release checks remain open. Keep the raw execution evidence outside the
public repository when it contains local paths, account context or private project content.
