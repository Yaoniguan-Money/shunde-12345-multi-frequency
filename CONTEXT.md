# Shunde 12345 Multi-Frequency Analysis

This context distinguishes immutable citizen work orders from AI-derived event understanding and cross-work-order multi-frequency conclusions.

## Language

**Work Order**:
One immutable 12345 complaint record and the unit used to count complaint frequency.
_Avoid_: Event, complaint event

**Event Instance**:
An AI-derived representation of one independent real-world issue described inside a Work Order. One Work Order may contain multiple Event Instances.
_Avoid_: Complaint count, frequency

**Same Event**:
A relationship between Event Instances from different Work Orders that indicates they refer to the same real-world issue or handling chain.
_Avoid_: Text duplicate, same-work-order similarity

**Multi-Frequency Event**:
A cluster of related Event Instances spanning at least two distinct Work Orders. Its frequency is the distinct Work Order count, not the Event Instance count.
_Avoid_: Event count, member count without qualification

**Work Order Count**:
The number of distinct Work Orders represented by a Multi-Frequency Event.
_Avoid_: Event count

**Event Count**:
The number of Event Instances represented by a Multi-Frequency Event; this may exceed its Work Order Count.
_Avoid_: Complaint frequency

**Analysis Outcome**:
The auditable result of applying one analysis pipeline run to one Work Order: unprocessed, analyzed with events, analyzed with no event, or failed.
_Avoid_: Inferring analysis completion from Event Count

**Review Status**:
The human review conclusion for a Multi-Frequency Event, independent from its business handling progress.
_Avoid_: Handling status, AI confidence

**Occurrence Date**:
A calendar date explicitly recoverable from an Event Instance's business-time evidence; unknown when the evidence cannot determine a full date.
_Avoid_: Import time, database creation time
