import io
import pandas as pd

class FileParser:
    """Parses uploaded files (CSV, Excel) into raw text string for LLM consumption"""
    
    @staticmethod
    def parse_file(filename: str, content: bytes) -> str:
        """
        Parses a file's content based on its extension.
        Returns a formatted string representing the rows/steps.
        """
        ext = filename.split('.')[-1].lower()
        
        try:
            if ext == 'csv':
                df = pd.read_csv(io.BytesIO(content))
            elif ext in ['xls', 'xlsx']:
                df = pd.read_excel(io.BytesIO(content))
            elif ext == 'txt':
                return content.decode('utf-8')
            else:
                raise ValueError(f"Unsupported file format: {ext}")
                
            # Convert dataframe to a readable string format
            # e.g., Step 1: Navigate to Google, Step 2: ...
            parsed_text = ""
            for i, row in df.iterrows():
                # Join non-null values in the row
                row_vals = [str(val) for val in row if pd.notna(val)]
                if row_vals:
                    parsed_text += f"Step {i+1}: " + " | ".join(row_vals) + "\n"
            
            return parsed_text
            
        except Exception as e:
            raise RuntimeError(f"Error parsing file {filename}: {str(e)}")
