# English medical demo rehearsal

Production scripted client; real local HTTP/MCP; isolated synthetic live-demo-v2 data.
Service clock: 2026-10-13 09:00+08:00. English text delivery and verified receipt passed. No external model calls.

## Interaction 1: Book a cardiology appointment next Tuesday afternoon

This is a draft; no appointment has been booked. Select a time to request a formal confirmation card. Available times: option 1: 14:00; option 2: 15:00; option 3: 15:30; option 4: 16:00.

## Interaction 2: Only after 3 PM

This is a draft; no appointment has been booked. Select a time to request a formal confirmation card. Available times: option 1: 15:30; option 2: 16:00.

## Interaction 3: Wait, do I have any other appointments?

I found 3 appointment records, including any cancellations. The selected time does not overlap the active appointments in this lookup. Available times: option 1: 15:30; option 2: 16:00.

## Interaction 4: Will that clash with my existing appointments?

I found 3 appointment records, including any cancellations. The selected time does not overlap the active appointments in this lookup. Available times: option 1: 15:30; option 2: 16:00.

## Interaction 5: Go back to the appointment we were booking

This is a draft; no appointment has been booked. Select a time to request a formal confirmation card. Available times: option 1: 15:30; option 2: 16:00.

## Interaction 6: The 3:30 PM one, please

No appointment has been booked yet. Review Cardiology on 2026-10-20 at 15:30, then click Approve booking to submit.

## Interaction 7: Click Approve

Your appointment is confirmed. Receipt reference: MED-REG-0001.

## Interaction 8: Click Approve

Your appointment is confirmed. Receipt reference: MED-REG-0001.

One write dispatch; one newly created booking; duplicate approval returned the same receipt.
This is a scripted rehearsal, not a real-model or microphone/STT accuracy measurement.