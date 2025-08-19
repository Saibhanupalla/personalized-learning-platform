# backend/vector_db.py
import os
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

# --- Initialize Connections ---
# Initialize Pinecone client
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

# Initialize the sentence transformer model
# This model converts text into 384-dimensional vectors
model = SentenceTransformer('all-MiniLM-L6-v2')

INDEX_NAME = "learning-platform"

# --- Create Pinecone Index if it doesn't exist ---
if INDEX_NAME not in pc.list_indexes().names():
    print(f"Creating new Pinecone index: {INDEX_NAME}")
    pc.create_index(
        name=INDEX_NAME,
        dimension=384, # Corresponds to the model's output dimension
        metric='cosine',
        spec=ServerlessSpec(
            cloud='aws', # You can change this to 'gcp' or 'azure' if needed
            region='us-east-1'
        )
    )

# Connect to the index
index = pc.Index(INDEX_NAME)

def upsert_lesson(lesson_id: int, lesson_text: str):
    """Creates a vector embedding and upserts it into Pinecone."""
    try:
        # Create the vector embedding
        vector = model.encode(lesson_text).tolist()
        
        # Upsert the vector into the Pinecone index
        # The ID must be a string
        index.upsert(vectors=[{"id": str(lesson_id), "values": vector}])
        print(f"Successfully upserted lesson {lesson_id} into Pinecone.")
    except Exception as e:
        print(f"Error upserting lesson to Pinecone: {e}")

def find_similar_lessons(lesson_id: int, top_k: int = 5):
    """Finds lessons with similar content using Pinecone."""
    try:
        # First, fetch the vector for the given lesson_id to use in the query
        fetch_response = index.fetch(ids=[str(lesson_id)])
        source_vector_data = fetch_response.vectors.get(str(lesson_id))

        if not source_vector_data:
            print(f"Vector for lesson {lesson_id} not found in Pinecone.")
            return []

        source_vector = source_vector_data.values

        # Query Pinecone for the most similar vectors
        query_response = index.query(
            vector=source_vector,
            top_k=top_k, # Fetch the top 5 most similar items
            include_values=False # We only need the IDs
        )
        
        # Extract the IDs, convert them back to integers, and exclude the original lesson ID
        similar_lesson_ids = [
            int(match['id']) for match in query_response['matches'] 
            if int(match['id']) != lesson_id
        ]
        
        return similar_lesson_ids
    except Exception as e:
        print(f"Error querying Pinecone: {e}")
        return []
