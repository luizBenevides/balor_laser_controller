import pypdf
import re

class PDFSerialExtractor:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.serials = []

    def extract_serials(self, pattern=r'[A-Z0-9]{5,20}'):
        """
        Extracts strings matching a pattern from the PDF.
        """
        self.serials = []
        try:
            reader = pypdf.PdfReader(self.pdf_path)
            for page in reader.pages:
                text = page.extract_text()
                # Find all matches for the serial pattern
                matches = re.findall(pattern, text)
                self.serials.extend(matches)
        except Exception as e:
            print(f"Error reading PDF: {e}")
        
        # Remove duplicates while preserving order
        seen = set()
        self.serials = [x for x in self.serials if not (x in seen or seen.add(x))]
        return self.serials

if __name__ == "__main__":
    # This needs a real PDF to test
    # extractor = PDFSerialExtractor("example.pdf")
    # print(extractor.extract_serials())
    pass
