# LinkedIn draft

500 of 1,500 answer pairs (33.3%) changed judge preference when answer order was swapped.

I ran blame on published Arena-Hard v0.1 results: the same generated answers, judged against the same baseline in both orders. 268 pairs reversed winner outright; 232 moved between a tie and a win or loss.

One judge praised a regex for not assuming a fixed video ID length. After the swap, it preferred the other answer for assuming that length. Both answers also missed part of the request.

blame is a local Python CLI that groups lost eval credit and puts the evidence beside each flag. It reads JSONL or Inspect text JSON and writes HTML, Markdown and JSON reports. No model API calls.

The limit: a disagreement is a lead to review, not proof that the eval caused the loss. Codex checked 20 fired verdicts against their documented predicates. That is not independent human validation or measured attribution accuracy.

The repo includes the findings, quoted examples and a small HTML preview. Repo link in the first comment.

#LLMEvals

What do you check before treating a lower eval score as a model regression?

## First comment

Repo, findings and report preview: REPO_URL

Editor note: replace `<REPO_URL>` with the public repository URL before posting. This checkout has no git remote configured. The post above is 1109 characters, including newlines; the first comment and this note are excluded.
