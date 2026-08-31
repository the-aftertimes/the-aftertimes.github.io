

def test_flat_block_names_the_fault_and_forbids_reuse():
    import write
    block = write.flat_block([
        {"line": '"No one wants to wake up at three in the morning."',
         "why": "the source is explaining the joke to the reader"}])
    assert "No one wants to wake up" in block
    assert "the source is explaining the joke to the reader" in block
    # The pool is bad writing, so the framing must forbid lifting it. funny_block
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
