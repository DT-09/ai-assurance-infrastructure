# Live Runtime Demo

1. Start FastAPI with the normal project command.
2. Open `/runtime.html`.
3. Register the `support-agent` authority contract.
4. Submit the `$25,000` refund action.
5. AAI returns `BLOCK` because the autonomous limit is `$5,000`.
6. Change the amount to `$100` and submit. AAI returns `REQUIRE_APPROVAL`.
7. Approve it and re-check. AAI returns `ALLOW`.

The decision is produced by the runtime gateway and persisted as evidence; the UI does not calculate the result.
