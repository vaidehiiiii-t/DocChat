from app.services.chunking import ChunkingService


def test_chunking_indices_and_page_numbers():
    service = ChunkingService(chunk_size=100, chunk_overlap=20, min_chunk_chars=20)

    # 3 pages with content
    p1 = "Apple pie is a delicious dessert made with fresh apples, cinnamon, and a golden flaky crust baked to perfection."
    p2 = "Banana bread is a moist quick bread made from mashed ripe bananas, walnuts, brown sugar, and vanilla extract."
    p3 = "Carrot cake features grated carrots, warm spices like nutmeg and cinnamon, and a rich cream cheese frosting."

    pages = [(1, p1), (2, p2), (3, p3)]
    chunks = service.chunk_pages(pages)

    assert len(chunks) >= 3

    # Check contiguous indexing from 0
    for idx, c in enumerate(chunks):
        assert c.chunk_index == idx
        assert c.char_count == len(c.text)
        assert c.char_count >= 20

    # Check page numbers
    page_1_chunks = [c for c in chunks if c.page_number == 1]
    page_2_chunks = [c for c in chunks if c.page_number == 2]
    page_3_chunks = [c for c in chunks if c.page_number == 3]

    assert len(page_1_chunks) > 0
    assert len(page_2_chunks) > 0
    assert len(page_3_chunks) > 0

    assert "Apple pie" in page_1_chunks[0].text
    assert "Banana bread" in page_2_chunks[0].text
    assert "Carrot cake" in page_3_chunks[0].text


def test_chunk_size_and_overlap():
    chunk_size = 200
    chunk_overlap = 50
    service = ChunkingService(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap, min_chunk_chars=20
    )

    # Long text exceeding chunk_size
    long_paragraph = (
        "Artificial intelligence and machine learning have transformed modern software engineering. "
        "Engineers now build retrieval augmented generation systems combining vector databases "
        "and large language models. Documents are chunked into smaller passages, embedded with "
        "dense transformer representations, and indexed for high performance cosine similarity queries. "
        "This allows contextual grounded generation with accurate source citations and minimal hallucination."
    )

    chunks = service.chunk_pages([(1, long_paragraph)])
    assert len(chunks) >= 2

    # Check that each chunk length does not exceed chunk_size + reasonable tolerance (e.g. word boundary)
    for c in chunks:
        assert c.char_count <= chunk_size + 20

    # Check that overlap exists between consecutive chunks from the same page
    for i in range(len(chunks) - 1):
        c1 = chunks[i].text
        c2 = chunks[i + 1].text
        # Common suffix/prefix overlap or shared words
        words_c1 = set(c1.split()[-6:])
        words_c2 = set(c2.split()[:6])
        overlap_words = words_c1.intersection(words_c2)
        assert len(overlap_words) > 0, "Expected overlap between consecutive chunks"


def test_filter_short_chunks():
    service = ChunkingService(chunk_size=500, chunk_overlap=50, min_chunk_chars=20)
    pages = [
        (1, "Too short"),  # < 20 chars
        (2, "   \n\t   "),  # whitespace
        (3, "This is a sufficiently long sentence that has more than twenty characters."),
    ]
    chunks = service.chunk_pages(pages)
    assert len(chunks) == 1
    assert chunks[0].page_number == 3
    assert chunks[0].chunk_index == 0


def test_empty_pages():
    service = ChunkingService()
    chunks = service.chunk_pages([])
    assert chunks == []
