# Knowledge Consumption

After mandatory authority reads and before freezing plan sources, VDD invokes
the repository Knowledge Locator through its trusted adapter policy. Locator
results are location-only recommendations. VDD rereads each recommended source
and records an adapter-owned accepted or rejected decision bound to its hash.

Required knowledge modules must have an accepted decision. An insufficient
optional module remains explicit and non-authorizing. VDD still reads user
input, repository rules, lifecycle authority, and direct source evidence; the
knowledge projection never replaces them.
