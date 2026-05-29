from togra.fs.hashing import compute_file_hash, hash_bytes


def test_hash_bytes_known_value():
    # echo -n "hello" | sha256sum
    assert (
        hash_bytes(b"hello")
        == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )


def test_compute_file_hash_matches_in_memory(tmp_path):
    p = tmp_path / "f.txt"
    p.write_bytes(b"abc" * 5000)
    assert compute_file_hash(p) == hash_bytes(b"abc" * 5000)


def test_hash_changes_when_file_changes(tmp_path):
    p = tmp_path / "x.txt"
    p.write_bytes(b"v1")
    h1 = compute_file_hash(p)
    p.write_bytes(b"v2")
    assert h1 != compute_file_hash(p)
