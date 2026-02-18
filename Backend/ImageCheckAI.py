from transformers import pipeline
from PIL import Image

# Load detector
detector = pipeline(
    "image-classification",
    model="capcheck/ai-human-generated-image-detection"
)

# Load image
image = Image.open(r"C:\Users\Home\Downloads\picture-lake.jpg")

# Run detection
result = detector(image)

# Print result
print(result)
