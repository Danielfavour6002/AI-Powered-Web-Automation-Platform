import io
from typing import List, Dict, Any, Optional
import pandas as pd

class FileParser:
    """Parses uploaded files (CSV, Excel, TXT) into structured grid or raw text."""
    
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
            parsed_text = ""
            for i, row in df.iterrows():
                row_vals = [str(val) for val in row if pd.notna(val)]
                if row_vals:
                    parsed_text += f"Step {i+1}: " + " | ".join(row_vals) + "\n"
            
            return parsed_text
            
        except Exception as e:
            raise RuntimeError(f"Error parsing file {filename}: {str(e)}")

    @staticmethod
    def get_sheets(filename: str, content: bytes) -> List[str]:
        """Get names of sheets inside a multi-tab Excel workbook."""
        ext = filename.split('.')[-1].lower()
        if ext not in ['xls', 'xlsx']:
            return []
        try:
            xl = pd.ExcelFile(io.BytesIO(content))
            return xl.sheet_names
        except Exception as e:
            raise RuntimeError(f"Error listing Excel sheets: {e}")

    @staticmethod
    def parse_to_grid(filename: str, content: bytes, sheet_name: Optional[str] = None, has_header: bool = True) -> Dict[str, Any]:
        """
        Parse file into raw rows and columns grid for preview,
        supporting sheet selectors and header toggling.
        """
        ext = filename.split('.')[-1].lower()
        try:
            if ext == 'csv':
                df = pd.read_csv(io.BytesIO(content), header=0 if has_header else None)
            elif ext in ['xls', 'xlsx']:
                # Read selected sheet or default to first
                df = pd.read_excel(io.BytesIO(content), sheet_name=sheet_name or 0, header=0 if has_header else None)
            elif ext == 'txt':
                lines = content.decode('utf-8').splitlines()
                # Create a simple 1-column dataframe
                df = pd.DataFrame(lines, columns=["Steps"])
            else:
                raise ValueError(f"Unsupported format: {ext}")
                
            # Convert NaN to empty string
            df = df.fillna("")
            
            # Map columns and grid rows
            headers = [str(col) for col in df.columns] if has_header else [f"Col {i+1}" for i in range(len(df.columns))]
            rows = df.values.tolist()
            
            # Convert values to strings
            rows_str = []
            for r in rows:
                rows_str.append([str(val) for val in r])
                
            return {
                "headers": headers,
                "rows": rows_str
            }
        except Exception as e:
            raise RuntimeError(f"Failed parsing to preview grid: {e}")

