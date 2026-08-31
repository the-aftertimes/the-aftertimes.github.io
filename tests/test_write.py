"""The write prompt is assembled here."""


def test_flat_block_names_the_fault_and_forbids_reuse():
    import write
    block = write.flat_block([
        {"line": '"No one wants to wake up at three in the morning."',
         "why": "the source is explaining the joke to the reader"}])
    assert "No one wants to wake up" in block
    assert "the source is explaining the joke to the reader" in block
    # The pool IS bad writing, so the framing must forbid lifting it. funny_block
    # records a model copying an example verbatim; from THIS pool that is worse.
    assert "Do not reuse" in block
    assert '""' not in block, "a quoted line must not end up double-quoted"


def test_flat_block_is_empty_without_a_pool():
    import write
    assert write.flat_block([]) == ""


def test_flat_block_is_capped():
    import write
    many = [{"line": f"line {i}", "why": "w"} for i in range(40)]
    assert write.flat_block(many).count(" - w") <= 6


def test_the_technique_reaches_the_write_prompt():
    """Techniques are about HOW a piece is built, so unlike engines - which steer
    ideate - they have to land in the WRITE prompt. A premise has no structure."""
    import write
    p = write.build_prompt("a premise", {"year": 2400, "years_from_now": 374},
                           "transport", "a style",
                           technique={"guidance": "ESCALATE BY DEGREE",
                                      "example": "The queue is in its fourth generation."})
    assert "ESCALATE BY DEGREE" in p
    assert "COMIC TECHNIQUE" in p
    # The example matters more than the guidance - few-shots dominate
    # instructions - but it must be labelled do-not-reuse.
    assert "fourth generation" in p and "never the words" in p


def test_no_technique_leaves_the_prompt_alone():
    import write
    dl = {"year": 2400, "years_from_now": 374}
    assert "COMIC TECHNIQUE" not in write.build_prompt("p", dl, "d", "s")
