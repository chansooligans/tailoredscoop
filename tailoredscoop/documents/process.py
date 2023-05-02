def split_text_into_chunks(text, max_chunk_size=2000):
    chunks = []
    current_chunk = ""

    # Split the text into words
    words = text.split()

    for word in words:
        # If adding the current word exceeds the maximum chunk size, start a new chunk
        if len(current_chunk) + len(word) + 1 > max_chunk_size:
            chunks.append(current_chunk.strip())
            current_chunk = ""

        # Add the word to the current chunk
        current_chunk += word + " "

    # Append the last chunk
    chunks.append(current_chunk.strip())

    return chunks