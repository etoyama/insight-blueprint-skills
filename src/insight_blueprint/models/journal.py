"""The parts of a journal that carry rules. A journal has no schema of its own.

Skills write the events of ``{id}_journal.yaml`` by hand. Three metadata keys
mark an event that decides the stage of an analysis, and only the commands of
design_io write them (ADR-0064 8, ADR-0067). They live here, in the package
the pre-write hook can import, so the hook and the stage rule read one list.
"""

# A confirmation asked of the analyst, the analyst's answer to one, and the
# reason an analysis was stopped.
JOURNAL_MARKS = ("asks_analyst", "answers", "stopped")

# The types of event a rule reads. A journal may hold other types: these are
# the ones the stage of an analysis, the open questions and the tree's checks
# tell apart, so each reader names them from here.
QUESTION = "question"
DECIDE = "decide"
CONCLUDE = "conclude"
# What /analysis-design copies in before premortem: an answer the analyst heard,
# which does not mean the analysis ran.
HEARING = "hearing"
