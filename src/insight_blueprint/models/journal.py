"""The parts of a journal that carry rules. A journal has no schema of its own.

Skills write the events of ``{id}_journal.yaml`` by hand. Three metadata keys
mark an event that decides the stage of an analysis, and only the commands of
design_io write them (ADR-0064 8, ADR-0067). They live here, in the package
the pre-write hook can import, so the hook and the stage rule read one list.
"""

# A confirmation asked of the analyst, the analyst's answer to one, and the
# reason an analysis was stopped.
JOURNAL_MARKS = ("asks_analyst", "answers", "stopped")
