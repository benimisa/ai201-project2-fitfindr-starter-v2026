# Acceptance criteria — FitFindr

Five criteria that say what "working" means for this agent, written in unit 3
**before** any results existed.

An acceptance criterion names a target: a number, a count, a rate, or something
a person could plainly observe. *"The agent handles errors"* is an opinion.
*"When search returns nothing, the agent stops before calling the second tool,
in 5 of 5 tries"* is a criterion.

Under each one, write a sentence or two on **why that target** and not a
stricter one. A reason that says something about your tools, your loop, or the
data earns credit; *"80% seemed reasonable"* does not.

> Missing your own targets next unit costs you nothing. Setting a target so
> easy you can't miss it does.

**Two are written for you. You write three.**

---

## 1. A matching query completes all three tools

Given a query that matches at least one listing, the agent completes all three
tool calls and returns a fit card — in at least 4 of 5 tries.

**Why this target:** My search is whole-word keyword overlap against the
title, description and tags, so a phrasing the data does not use ("tee shirt"
for a listing tagged "graphic tee", "trainers" for "sneakers") returns nothing
and the run stops at the branch. The two model calls can also fail once in a
while when a rate-limit retry runs out. One miss in five leaves room for those
without hiding a loop that is actually broken.

---

## 2. An impossible query stops before the second tool

Given a query that matches no listings, the agent stops before calling
`suggest_outfit` and returns a message naming what to change — 5 of 5 tries.

**Why this target:** The empty branch is a single `if` on whether
`session["search_results"]` is an empty list, and it runs before any model
call, so nothing in this path varies between tries. If it fails even once,
the loop is wrong, not unlucky.

---

## 3. The item the search found is the item the next tool received

For a query that matches, the `id` of the listing in `session["selected_item"]`
is the same `id` as `session["search_results"][0]` and the same `id` as the
item passed to `suggest_outfit` (visible as that step's input in the loop
trace), and the fit card contains that listing's title — in 5 of 5 tries.

**Why this target:** The item travels through one dict with no model call in
between, so there is no randomness to allow for and 5 of 5 is the only honest
number. The fit card check is the part a person can see without reading code:
if the card names a different item than the session holds, the state was
overwritten somewhere between the search and the card, and that would look
like a fit card problem when it is really a state problem.

---

## 4. The fit card names the deal and does not repeat itself

Running the same matching query 5 times with the cache off, every one of the
5 fit cards mentions the item's price as a dollar amount and its platform, and
no two of the 5 cards start with the same opening sentence — 5 of 5 cards for
the mentions, 0 repeated openings.

**Why this target:** The price and platform are written into the prompt, so a
card without them is a prompt failure rather than model variety, and 5 of 5 is
fair. The opening-sentence check is what "different each time" means in a form
I can count; with `TEMPERATURE` at 0.9 identical openings should be rare, and
if they do repeat the first thing to check is whether the cache was on. I did
not set a length target, because a card with a fifth sentence is not something
a user would call broken.

---

## 5. The search respects the price ceiling

For any query that states a ceiling as "under $N", `session["parsed"]["max_price"]`
equals N and every listing in `session["search_results"]` has `price <= N` —
in 5 of 5 tries.

**Why this target:** The filter is one comparison with no model call, so it
should never miss, and a weaker target would only hide a bug. The failure it
catches is a silent one: if the parser drops the price (the PowerShell `$30`
trap, or a phrasing like "under 30 dollars"), the search runs with no ceiling
and returns items the user said they could not afford, with no error to say
so. Checking `parsed` as well as the results tells me which half failed.

---

<!-- ─────────────────────────────────────────────────────────────────────────
     UNIT 4 — read this before you change anything above.

     If a criterion turns out to be BROKEN rather than merely unmet, you can
     revise it, and that earns credit. But never delete or edit the original
     line. Add the revision underneath it, like this:

         ## 4. Something about the fit card

         The fit card is different every time.

         **Why this target:** ...

         > **Revised in unit 4:** For 5 different items, the 5 fit cards share
         > no opening sentence.
         >
         > **Why revised:** "different" wasn't checkable — two cards that
         > differed by one word still counted. The new version is something I
         > can actually score.

     That's a revision because the criterion couldn't be MEASURED.

     Lowering a target because you missed it is not a revision, and it costs
     you the point:

         ✗ "I said the empty search stops it 5 of 5 times, but I got 3 of 5,
            so 3 of 5 is more realistic."

     A number you missed stays where it is, gets diagnosed, and gets a fix
     attempted. That's where the points are.
     ───────────────────────────────────────────────────────────────────────── -->
