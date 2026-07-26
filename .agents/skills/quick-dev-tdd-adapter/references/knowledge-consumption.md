# Verify-Bound Knowledge Consumption

Quick Dev consumes the VDD-frozen accepted knowledge decisions and their source
hashes. It does not issue a new Locator request, add a candidate, reclassify a
decision, widen a path policy, or add a satisfied module. Any mismatch routes
to VDD repair before RED.
