import re
from typing import Dict, List, Tuple, Optional
from question_parser import QuestionParser

class ImprovedQuestionParser(QuestionParser):
    """
    Improved question parser that handles double spaces and other formatting issues
    """
    
    def __init__(self):
        super().__init__()
        
        # Common text preprocessing patterns
        self.preprocessing_patterns = [
            # Multiple spaces to single space
            (r'\s+', ' '),
            # Fix common word spacing issues
            (r'  facing', ' facing'),
            (r'  cone', ' cone'),
            (r'  cube', ' cube'),
            (r'  cylinder', ' cylinder'),
            (r'  sphere', ' sphere'),
            # Fix spacing around numbers
            (r'number\s+(\d+)', r'number \1'),
            # Fix spacing around colors
            (r'(red|blue|green|yellow|grey|gray)\s+', r'\1 '),
            # Fix spacing around case keywords
            (r'(uppercase|lowercase)\s+', r'\1 '),
        ]
        
        # Enhanced shape recognition with common variations
        self.shape_variations = {
            'cube': ['cube', 'box', 'square'],
            'sphere': ['sphere', 'ball', 'circle'],
            'cylinder': ['cylinder', 'tube', 'pipe'],
            'cone': ['cone', 'triangle', 'pyramid']
        }
        
        # Shape similarity mapping for fallback matching
        self.shape_similarity = {
            'sphere': ['sphere', 'circle'],
            'circle': ['sphere', 'circle'],
            'cube': ['cube', 'square'],
            'square': ['cube', 'square']
        }
        
        # Enhanced character similarity mapping (includes case variations)
        self.character_similarity = {
            # Numbers and letters that look similar
            'o': ['0', 'o', 'O'],
            'O': ['0', 'o', 'O'],
            '0': ['0', 'o', 'O'],
            'i': ['1', 'i', 'I', 'l', 'L'],
            'I': ['1', 'i', 'I', 'l', 'L'],
            'l': ['1', 'i', 'I', 'l', 'L'],
            'L': ['1', 'i', 'I', 'l', 'L'],
            '1': ['1', 'i', 'I', 'l', 'L'],
            's': ['5', 's', 'S'],
            'S': ['5', 's', 'S'],
            '5': ['5', 's', 'S'],
            'z': ['2', 'z', 'Z'],
            'Z': ['2', 'z', 'Z'],
            '2': ['2', 'z', 'Z'],
            'g': ['6', 'g', 'G'],
            'G': ['6', 'g', 'G'],
            '6': ['6', 'g', 'G'],
            'b': ['8', 'b', 'B'],
            'B': ['8', 'b', 'B'],
            '8': ['8', 'b', 'B'],
            # Case variations for all letters
            'c': ['c', 'C'], 'C': ['c', 'C'],
            'h': ['h', 'H'], 'H': ['h', 'H'],
            'j': ['j', 'J'], 'J': ['j', 'J'],
            'k': ['k', 'K'], 'K': ['k', 'K'],
            'p': ['p', 'P'], 'P': ['p', 'P'],
            'u': ['u', 'U'], 'U': ['u', 'U'],
            'v': ['v', 'V'], 'V': ['v', 'V'],
            'w': ['w', 'W'], 'W': ['w', 'W'],
            'x': ['x', 'X'], 'X': ['x', 'X'],
        }
        
        # Enhanced error correction patterns
        self.error_corrections = {
            # Spelling corrections
            'upppercase': 'uppercase',
            'lowwercase': 'lowercase',
            'sieway': 'sideway',
            'frront': 'front',
            'grray': 'gray',
            'gre': 'gray',
            'bluw': 'blue',
            'grene': 'green',
            'yelow': 'yellow',
            'yelllow': 'yellow',
            
            # Common OCR/typo corrections
            'rnatches': 'matches',
            'orientaion': 'orientation',
            'colr': 'color',
            'facng': 'facing',
            
            # Word boundary fixes
            'thelowercase': 'the lowercase',
            'theuppercase': 'the uppercase',
            'thenumber': 'the number',
        }
    
    def preprocess_question(self, question: str) -> str:
        """
        Preprocess question text to handle common formatting issues
        
        Args:
            question: Raw question string
            
        Returns:
            Cleaned question string
        """
        if not question:
            return ""
            
        # Start with the original question
        cleaned = question.strip()
        
        # Apply preprocessing patterns
        for pattern, replacement in self.preprocessing_patterns:
            cleaned = re.sub(pattern, replacement, cleaned)
        
        # Apply error corrections
        for error, correction in self.error_corrections.items():
            cleaned = re.sub(r'\b' + re.escape(error) + r'\b', correction, cleaned, flags=re.IGNORECASE)
        
        # Final cleanup
        cleaned = ' '.join(cleaned.split())  # Remove extra whitespace
        cleaned = cleaned.strip()
        
        return cleaned
    
    def parse_class_name(self, class_name: str) -> Optional[Dict]:
        """
        Parse a class name with custom typo tolerance (e.g., 'rey_front_y' -> 'grey_front_y')
        """
        if not class_name:
            return None
            
        original_class = class_name
        
        # Preprocess the class name to correct common spelling/formatting typos
        # Class 1 fix: 'rey_front_y' -> 'grey_front_y'
        if class_name.startswith('rey_'):
            class_name = class_name.replace('rey_', 'grey_', 1)
        elif class_name.startswith('gray_'):
            class_name = class_name.replace('gray_', 'grey_', 1)
            
        # Parse using parent QuestionParser method
        parsed = super().parse_class_name(class_name)
        
        if parsed:
            # Preserve original class name in the parsed info
            parsed['original'] = original_class
            
        return parsed
    
    def parse_question(self, question: str) -> Dict:
        """
        Enhanced question parsing with preprocessing
        
        Args:
            question: Question string
            
        Returns:
            Dictionary with parsed question components
        """
        # Preprocess the question first
        cleaned_question = self.preprocess_question(question)
        
        # Call parent class method with cleaned question
        result = super().parse_question(cleaned_question)
        
        # Add preprocessing info to result
        result['original_question'] = question
        result['cleaned_question'] = cleaned_question
        result['preprocessing_applied'] = question != cleaned_question
        
        return result
    
    def _parse_description(self, description: str) -> Dict:
        """
        Enhanced description parsing with better shape recognition
        """
        # First preprocess the description
        description = self.preprocess_question(description)
        
        # Call parent method
        result = super()._parse_description(description)
        
        # Enhanced shape recognition
        if not result['character'] or result['type'] != 'shape':
            # Try to match shape variations
            desc_lower = description.lower()
            for standard_shape, variations in self.shape_variations.items():
                for variation in variations:
                    if variation in desc_lower:
                        result['character'] = standard_shape
                        result['type'] = 'shape'
                        result['case'] = None
                        break
                if result['character'] == standard_shape:
                    break
        
        return result
    
    def _find_orientation_match(self, parsed_question: Dict, parsed_detections: List[Dict]) -> Optional[Dict]:
        """Find target that matches orientation of reference with fallback logic"""
        # First find the reference object
        reference_matches = []
        for item in parsed_detections:
            parsed = item['parsed']
            if self._matches_criteria(parsed,
                                    parsed_question['reference_character'],
                                    parsed_question['reference_case'],
                                    parsed_question['reference_type']):
                reference_matches.append(item)
        
        if not reference_matches:
            return None
        
        # Get the orientation from reference (use first match)
        reference_orientation = reference_matches[0]['parsed']['orientation']
        
        # Now find target with that orientation
        exact_matches = []
        partial_matches = []
        
        for item in parsed_detections:
            parsed = item['parsed']
            
            # Check if it matches the target criteria (character, case, type)
            criteria_match = self._matches_criteria(parsed,
                                                  parsed_question['target_character'],
                                                  parsed_question['target_case'],
                                                  parsed_question['target_type'])
            
            if criteria_match:
                if parsed['orientation'] == reference_orientation:
                    exact_matches.append(item)
                else:
                    partial_matches.append(item)
        
        # Return exact match if available
        if exact_matches:
            return exact_matches[0]['detection']
        
        # Fallback: return partial match if no exact match
        # This handles cases where shape/character exists but orientation doesn't match
        if partial_matches:
            return partial_matches[0]['detection']
        
        return None
    
    def _find_color_match(self, parsed_question: Dict, parsed_detections: List[Dict]) -> Optional[Dict]:
        """Find target that matches color of reference with fallback logic"""
        # First find the reference object
        reference_matches = []
        for item in parsed_detections:
            parsed = item['parsed']
            if self._matches_criteria(parsed,
                                    parsed_question['reference_character'],
                                    parsed_question['reference_case'],
                                    parsed_question['reference_type']):
                reference_matches.append(item)
        
        if not reference_matches:
            return None
        
        # Get the color from reference (use first match)
        reference_color = reference_matches[0]['parsed']['color']
        
        # Now find target with that color
        exact_matches = []
        partial_matches = []
        
        for item in parsed_detections:
            parsed = item['parsed']
            
            # Check if it matches the target criteria (character, case, type)
            criteria_match = self._matches_criteria(parsed,
                                                  parsed_question['target_character'],
                                                  parsed_question['target_case'],
                                                  parsed_question['target_type'])
            
            if criteria_match:
                if parsed['color'] == reference_color:
                    exact_matches.append(item)
                else:
                    partial_matches.append(item)
        
        # Return exact match if available
        if exact_matches:
            return exact_matches[0]['detection']
        
        # Fallback: return partial match if no exact match
        # This handles cases where shape/character exists but color doesn't match
        if partial_matches:
            return partial_matches[0]['detection']
        
        return None
    
    def _find_direct_match(self, parsed_question: Dict, parsed_detections: List[Dict]) -> Optional[Dict]:
        """Find target that directly matches criteria with fallback logic"""
        exact_matches = []
        partial_matches = []
        
        for item in parsed_detections:
            parsed = item['parsed']
            
            # Check if it matches the character criteria
            criteria_match = self._matches_criteria(parsed,
                                                  parsed_question['target_character'],
                                                  parsed_question['target_case'],
                                                  parsed_question['target_type'])
            
            if criteria_match:
                # Check all other criteria
                color_match = not parsed_question['target_color'] or parsed['color'] == parsed_question['target_color']
                orientation_match = not parsed_question['target_orientation'] or parsed['orientation'] == parsed_question['target_orientation']
                
                if color_match and orientation_match:
                    exact_matches.append(item)
                elif color_match:  # Character and color match, but not orientation
                    partial_matches.append(item)
        
        # Return exact match if available
        if exact_matches:
            return exact_matches[0]['detection']
        
        # Fallback: return partial match if no exact match
        # This handles cases where character/case/color match but orientation doesn't
        if partial_matches:
            return partial_matches[0]['detection']
        
        # Call parent method for final fallback
        return super()._find_direct_match(parsed_question, parsed_detections)
    
    def _matches_criteria(self, parsed: Dict, character: str, case: str, char_type: str) -> bool:
        """Enhanced matching criteria with similarity support"""
        if character:
            # Use character similarity mapping for flexible matching
            target_char = character
            parsed_char = parsed['character']
            
            # Check direct match first
            if parsed_char == target_char:
                pass  # Direct match
            # Check character similarity
            elif target_char in self.character_similarity:
                if parsed_char not in self.character_similarity[target_char]:
                    return False
            else:
                return False
        
        # Enhanced case checking with fallback
        if case and parsed.get('case'):
            if parsed['case'] != case:
                # For letters, try case-insensitive matching as fallback
                if char_type == 'letter':
                    # Allow case mismatch for letters as a fallback
                    pass
                else:
                    return False
        
        # Enhanced type checking with shape similarity
        if char_type:
            parsed_type = parsed['type']
            parsed_character = parsed['character']
            
            # Direct type match
            if parsed_type == char_type:
                pass
            # Shape similarity matching
            elif char_type == 'shape' and parsed_type == 'shape':
                if character in self.shape_similarity:
                    if parsed_character not in self.shape_similarity[character]:
                        return False
                else:
                    return False
            # Character-number ambiguity (already handled above)
            elif character and character in self.character_similarity:
                # Allow type flexibility for ambiguous characters
                pass
            else:
                return False
        
        return True
    
    def analyze_questions_file(self, file_path: str) -> Dict:
        """
        Analyze a questions file for common issues and patterns
        
        Args:
            file_path: Path to questions file
            
        Returns:
            Analysis results dictionary
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except FileNotFoundError:
            return {'error': f'File not found: {file_path}'}
        except Exception as e:
            return {'error': f'Error reading file: {str(e)}'}
        
        questions = []
        for line in lines:
            line = line.strip()
            if '|' in line:
                # Extract question part after line number
                parts = line.split('|', 1)
                if len(parts) > 1:
                    question = parts[1].strip()
                    questions.append(question)
            elif line:
                questions.append(line)
        
        analysis = {
            'total_questions': len(questions),
            'preprocessing_issues': {
                'double_spaces': 0,
                'multiple_spaces': 0,
                'spelling_errors': 0,
                'formatting_issues': 0
            },
            'question_types': {
                'direct': 0,
                'direct_facing': 0,
                'color_match': 0,
                'orientation_match': 0,
                'malformed': 0
            },
            'common_issues': [],
            'sample_fixes': []
        }
        
        for i, question in enumerate(questions):
            if not question:
                continue
            
            # Check for preprocessing issues
            if '  ' in question:
                analysis['preprocessing_issues']['double_spaces'] += 1
            
            if re.search(r'\s{3,}', question):
                analysis['preprocessing_issues']['multiple_spaces'] += 1
            
            # Check for spelling errors
            for error in self.error_corrections:
                if error in question.lower():
                    analysis['preprocessing_issues']['spelling_errors'] += 1
                    break
            
            # Try to parse the question
            try:
                cleaned = self.preprocess_question(question)
                parsed = self.parse_question(question)
                
                # Classify question type
                q_type = parsed.get('question_type', 'malformed')
                if q_type in analysis['question_types']:
                    analysis['question_types'][q_type] += 1
                else:
                    analysis['question_types']['malformed'] += 1
                
                # Record sample fixes if preprocessing was applied
                if parsed.get('preprocessing_applied') and len(analysis['sample_fixes']) < 10:
                    analysis['sample_fixes'].append({
                        'line': i + 1,
                        'original': question,
                        'cleaned': cleaned
                    })
                    
            except Exception as e:
                analysis['question_types']['malformed'] += 1
                analysis['common_issues'].append({
                    'line': i + 1,
                    'question': question,
                    'error': str(e)
                })
        
        return analysis
    
    def generate_cleaning_report(self, file_path: str) -> str:
        """
        Generate a report showing cleaning suggestions for a questions file
        
        Args:
            file_path: Path to questions file
            
        Returns:
            Formatted report string
        """
        analysis = self.analyze_questions_file(file_path)
        
        if 'error' in analysis:
            return f"Error: {analysis['error']}"
        
        report = f"""
Question File Analysis Report
============================

File: {file_path}
Total Questions: {analysis['total_questions']}

PREPROCESSING ISSUES FOUND:
- Double spaces: {analysis['preprocessing_issues']['double_spaces']}
- Multiple spaces: {analysis['preprocessing_issues']['multiple_spaces']}
- Spelling errors: {analysis['preprocessing_issues']['spelling_errors']}
- Formatting issues: {analysis['preprocessing_issues']['formatting_issues']}

QUESTION TYPE DISTRIBUTION:
- Direct questions: {analysis['question_types']['direct']}
- Direct with facing: {analysis['question_types']['direct_facing']}
- Color match: {analysis['question_types']['color_match']}
- Orientation match: {analysis['question_types']['orientation_match']}
- Malformed: {analysis['question_types']['malformed']}

SAMPLE FIXES APPLIED:
"""
        
        for i, fix in enumerate(analysis['sample_fixes'][:10]):
            report += f"\nLine {fix['line']}:\n"
            report += f"  Original: {fix['original']}\n"
            report += f"  Cleaned:  {fix['cleaned']}\n"
        
        if analysis['common_issues']:
            report += f"\nCOMMON ISSUES ({len(analysis['common_issues'])} total):\n"
            for issue in analysis['common_issues'][:5]:
                report += f"  Line {issue['line']}: {issue['error']}\n"
                report += f"    Question: {issue['question']}\n"
        
        return report
    
    def clean_questions_file(self, input_file: str, output_file: str) -> Dict:
        """
        Clean a questions file and save the result
        
        Args:
            input_file: Input file path
            output_file: Output file path
            
        Returns:
            Dictionary with cleaning results
        """
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except FileNotFoundError:
            return {'error': f'Input file not found: {input_file}'}
        except Exception as e:
            return {'error': f'Error reading input file: {str(e)}'}
        
        cleaned_lines = []
        changes_made = 0
        
        for line in lines:
            original_line = line.rstrip('\r\n')
            
            if '|' in original_line:
                # Split line number and question
                parts = original_line.split('|', 1)
                if len(parts) > 1:
                    line_num = parts[0]
                    question = parts[1].strip()
                    
                    # Clean the question
                    cleaned_question = self.preprocess_question(question)
                    
                    # Reconstruct the line
                    cleaned_line = f"{line_num}|{cleaned_question}"
                    
                    if cleaned_line != original_line:
                        changes_made += 1
                    
                    cleaned_lines.append(cleaned_line)
                else:
                    cleaned_lines.append(original_line)
            else:
                # Process line without line number
                cleaned_line = self.preprocess_question(original_line)
                if cleaned_line != original_line:
                    changes_made += 1
                cleaned_lines.append(cleaned_line)
        
        # Write cleaned file
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                for line in cleaned_lines:
                    f.write(line + '\n')
        except Exception as e:
            return {'error': f'Error writing output file: {str(e)}'}
        
        return {
            'success': True,
            'total_lines': len(lines),
            'changes_made': changes_made,
            'output_file': output_file
        }


def main():
    """Test the improved parser"""
    parser = ImprovedQuestionParser()
    
    # Test preprocessing
    test_questions = [
        "click the lowercase j  facing front",
        "click the number 8 matches the orientation of  cone",
        "click the  cube matches the orientation of gray uppercase D",
        "click the upppercase K",
        "click the lowwercase h  facing sieway",
        "click the grray sphere",
        "click the blue   uppercase   K"
    ]
    
    print("Testing preprocessing:")
    for question in test_questions:
        cleaned = parser.preprocess_question(question)
        print(f"Original: {repr(question)}")
        print(f"Cleaned:  {repr(cleaned)}")
        print()
    
    # Test parsing
    print("Testing parsing:")
    for question in test_questions:
        result = parser.parse_question(question)
        print(f"Question: {question}")
        print(f"Result: {result}")
        print()
    
    # Test file analysis
    if __name__ == "__main__":
        import os
        if os.path.exists('questions.txt'):
            print("Analyzing questions.txt...")
            report = parser.generate_cleaning_report('questions.txt')
            print(report)
            
            # Offer to clean the file
            response = input("\nWould you like to create a cleaned version? (y/n): ")
            if response.lower() == 'y':
                result = parser.clean_questions_file('questions.txt', 'questions_cleaned.txt')
                if result.get('success'):
                    print(f"Success! Cleaned file saved as {result['output_file']}")
                    print(f"Changes made to {result['changes_made']} out of {result['total_lines']} lines")
                else:
                    print(f"Error: {result['error']}")

if __name__ == "__main__":
    main()
