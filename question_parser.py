import re
from typing import Dict, List, Tuple, Optional

class QuestionParser:
    def __init__(self):
        # Define the possible values for each component
        self.orientations = ['front', 'side']
        self.colors = ['grey', 'red', 'green', 'blue', 'yellow']
        self.shapes = ['cone', 'cube', 'cylinder', 'circle', 'sphere']
        
        # Pattern to parse class names
        self.class_pattern = r'^(red|green|blue|yellow|grey)_(front|side)_(.+)$'
        
    def parse_class_name(self, class_name: str) -> Optional[Dict]:
        """
        Parse a class name into its components
        
        Args:
            class_name: String like 'red_front_A' or 'blue_side_k'
            
        Returns:
            Dictionary with parsed components or None if invalid
        """
        # Handle special cases like 'class_58'
        if class_name.startswith('class_'):
            return None
            
        match = re.match(self.class_pattern, class_name)
        if not match:
            return None
            
        color, orientation, character = match.groups()
        
        # Determine if it's a shape, number, or letter
        if character in self.shapes:
            char_type = 'shape'
            case = None
        elif character.isdigit():
            char_type = 'number'
            case = None
        else:
            char_type = 'letter'
            case = 'uppercase' if character.isupper() else 'lowercase'
        
        return {
            'color': color,
            'orientation': orientation,
            'character': character,
            'type': char_type,
            'case': case,
            'original': class_name
        }
    
    def parse_question(self, question: str) -> Dict:
        """
        Parse a question to extract target criteria
        
        Args:
            question: Question string like "click the blue uppercase K"
            
        Returns:
            Dictionary with target criteria
        """
        question = question.lower().strip()
        
        # Initialize result
        result = {
            'target_color': None,
            'target_orientation': None,
            'target_character': None,
            'target_case': None,
            'target_type': None,
            'reference_color': None,
            'reference_orientation': None,
            'reference_character': None,
            'reference_case': None,
            'reference_type': None,
            'question_type': None
        }
        
        # Determine question type
        if ' matches the color of ' in question:
            result['question_type'] = 'color_match'
        elif ' matches the orientation of ' in question:
            result['question_type'] = 'orientation_match'
        elif ' facing front' in question:
            result['question_type'] = 'direct_front'
        elif ' facing sideway' in question:
            result['question_type'] = 'direct_side'
        else:
            result['question_type'] = 'direct'
        
        # Extract target information
        if result['question_type'] in ['color_match', 'orientation_match']:
            # Split on "matches the X of"
            if ' matches the color of ' in question:
                target_part, reference_part = question.split(' matches the color of ')
            else:
                target_part, reference_part = question.split(' matches the orientation of ')
            
            # Parse target
            target_info = self._parse_description(target_part.replace('click the ', ''))
            reference_info = self._parse_description(reference_part)
            
            # Set target info
            result['target_color'] = target_info['color']
            result['target_character'] = target_info['character']
            result['target_case'] = target_info['case']
            result['target_type'] = target_info['type']
            
            # Set reference info
            result['reference_color'] = reference_info['color']
            result['reference_character'] = reference_info['character']
            result['reference_case'] = reference_info['case']
            result['reference_type'] = reference_info['type']
            
        else:
            # Direct question
            target_text = question.replace('click the ', '')
            target_text = target_text.replace(' facing front', '').replace(' facing sideway', '')
            target_info = self._parse_description(target_text)
            
            result['target_color'] = target_info['color']
            result['target_character'] = target_info['character']
            result['target_case'] = target_info['case']
            result['target_type'] = target_info['type']
            
            # Set orientation for direct questions
            if ' facing front' in question:
                result['target_orientation'] = 'front'
            elif ' facing sideway' in question:
                result['target_orientation'] = 'side'
        
        return result
    
    def _parse_description(self, description: str) -> Dict:
        """
        Parse a description like "blue uppercase K" or "number 6"
        """
        description = description.strip()
        
        result = {
            'color': None,
            'character': None,
            'case': None,
            'type': None
        }
        
        # Extract color (handle gray/grey mapping)
        color_mapping = {
            'gray': 'grey',
            'grey': 'grey'
        }
        
        for color_variant in ['gray', 'grey', 'red', 'green', 'blue', 'yellow']:
            if color_variant in description:
                result['color'] = color_mapping.get(color_variant, color_variant)
                description = description.replace(color_variant, '').strip()
                break
        
        # Extract case and type
        if 'uppercase' in description:
            result['case'] = 'uppercase'
            description = description.replace('uppercase', '').strip()
            result['type'] = 'letter'
        elif 'lowercase' in description:
            result['case'] = 'lowercase'
            description = description.replace('lowercase', '').strip()
            result['type'] = 'letter'
        elif 'number' in description:
            result['type'] = 'number'
            description = description.replace('number', '').strip()
        
        # Extract character (what's left should be the character)
        description = description.strip()
        if description:
            # Handle shapes
            if description in self.shapes:
                result['character'] = description
                result['type'] = 'shape'
            else:
                result['character'] = description
                # If type not set, determine from character
                if result['type'] is None:
                    if description.isdigit():
                        result['type'] = 'number'
                    elif description in self.shapes:
                        result['type'] = 'shape'
                    else:
                        result['type'] = 'letter'
                        if result['case'] is None:
                            result['case'] = 'uppercase' if description.isupper() else 'lowercase'
        
        return result
    
    def find_target(self, question: str, detections: List[Dict]) -> Optional[Dict]:
        """
        Find the target detection based on the question
        
        Args:
            question: Question string
            detections: List of detection dictionaries from get_detections_info()
            
        Returns:
            The matching detection or None
        """
        parsed_question = self.parse_question(question)
        
        # Parse all detections
        parsed_detections = []
        for detection in detections:
            parsed_class = self.parse_class_name(detection['class_name'])
            if parsed_class:
                parsed_detections.append({
                    'detection': detection,
                    'parsed': parsed_class
                })
        
        # Find target based on question type
        if parsed_question['question_type'] == 'color_match':
            return self._find_color_match(parsed_question, parsed_detections)
        elif parsed_question['question_type'] == 'orientation_match':
            return self._find_orientation_match(parsed_question, parsed_detections)
        else:
            return self._find_direct_match(parsed_question, parsed_detections)
    
    def _find_color_match(self, parsed_question: Dict, parsed_detections: List[Dict]) -> Optional[Dict]:
        """Find target that matches color of reference"""
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
        for item in parsed_detections:
            parsed = item['parsed']
            if (parsed['color'] == reference_color and
                self._matches_criteria(parsed,
                                     parsed_question['target_character'],
                                     parsed_question['target_case'],
                                     parsed_question['target_type'])):
                return item['detection']
        
        return None
    
    def _find_orientation_match(self, parsed_question: Dict, parsed_detections: List[Dict]) -> Optional[Dict]:
        """Find target that matches orientation of reference"""
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
        for item in parsed_detections:
            parsed = item['parsed']
            if (parsed['orientation'] == reference_orientation and
                self._matches_criteria(parsed,
                                     parsed_question['target_character'],
                                     parsed_question['target_case'],
                                     parsed_question['target_type'])):
                return item['detection']
        
        return None
    
    def _find_direct_match(self, parsed_question: Dict, parsed_detections: List[Dict]) -> Optional[Dict]:
        """Find target that directly matches criteria"""
        # First try exact match
        for item in parsed_detections:
            parsed = item['parsed']
            
            # Check all criteria
            if parsed_question['target_color'] and parsed['color'] != parsed_question['target_color']:
                continue
            if parsed_question['target_orientation'] and parsed['orientation'] != parsed_question['target_orientation']:
                continue
            if not self._matches_criteria(parsed,
                                        parsed_question['target_character'],
                                        parsed_question['target_case'],
                                        parsed_question['target_type']):
                continue
            
            return item['detection']
        
        # If no exact match, try fallback with relaxed case matching
        return self._find_fallback_match(parsed_question, parsed_detections)
    
    def _find_fallback_match(self, parsed_question: Dict, parsed_detections: List[Dict]) -> Optional[Dict]:
        """Find target with relaxed criteria (fallback)"""
        fallback_candidates = []
        
        for item in parsed_detections:
            parsed = item['parsed']
            
            # Check color (strict)
            if parsed_question['target_color'] and parsed['color'] != parsed_question['target_color']:
                continue
                
            # Check orientation (strict)
            if parsed_question['target_orientation'] and parsed['orientation'] != parsed_question['target_orientation']:
                continue
            
            # Check character and type with relaxed case
            if self._matches_criteria_relaxed(parsed,
                                             parsed_question['target_character'],
                                             parsed_question['target_case'],
                                             parsed_question['target_type']):
                # Calculate match score based on how many criteria match exactly
                score = self._calculate_match_score(parsed, parsed_question)
                fallback_candidates.append((item['detection'], score))
        
        # Return the best fallback candidate
        if fallback_candidates:
            # Sort by score (higher is better)
            fallback_candidates.sort(key=lambda x: x[1], reverse=True)
            return fallback_candidates[0][0]
        
        return None
    
    def _matches_criteria_relaxed(self, parsed: Dict, character: str, case: str, char_type: str) -> bool:
        """Check if parsed object matches character criteria with relaxed case matching"""
        if character:
            # Handle character ambiguities (O/0, I/1, etc.)
            ambiguous_chars = {
                'o': ['0', 'o'],
                '0': ['0', 'o'],
                'i': ['1', 'i'],
                '1': ['1', 'i'],
                'l': ['1', 'l', 'i'],
                's': ['5', 's'],
                '5': ['5', 's'],
                'z': ['2', 'z'],
                '2': ['2', 'z']
            }
            
            target_char = character.lower()
            parsed_char = parsed['character'].lower()
            
            # Check direct match first
            if parsed_char == target_char:
                pass  # Direct match
            # Check ambiguous characters
            elif target_char in ambiguous_chars:
                if parsed_char not in ambiguous_chars[target_char]:
                    return False
            else:
                return False
        
        # RELAXED: Skip case checking in fallback mode
        # This allows uppercase/lowercase flexibility
        
        # For type checking, be more flexible with ambiguous characters
        if char_type and character:
            target_char = character.lower()
            # If we're looking for ambiguous characters, don't strictly enforce type
            if target_char in ['o', '0', 'i', '1', 'l', 's', '5', 'z', '2']:
                # Allow type flexibility for ambiguous characters
                pass
            elif parsed['type'] != char_type:
                return False
        elif char_type and parsed['type'] != char_type:
            return False
        
        return True
    
    def _calculate_match_score(self, parsed: Dict, parsed_question: Dict) -> float:
        """Calculate match score for fallback candidates"""
        score = 0.0
        
        # Color match (high priority)
        if parsed_question['target_color'] and parsed['color'] == parsed_question['target_color']:
            score += 3.0
        
        # Orientation match (high priority)
        if parsed_question['target_orientation'] and parsed['orientation'] == parsed_question['target_orientation']:
            score += 3.0
        
        # Character match (medium priority)
        if parsed_question['target_character']:
            if parsed['character'].lower() == parsed_question['target_character'].lower():
                score += 2.0
        
        # Case match (lower priority in fallback)
        if parsed_question['target_case'] and parsed['case'] == parsed_question['target_case']:
            score += 1.0
        
        # Type match (lower priority in fallback)
        if parsed_question['target_type'] and parsed['type'] == parsed_question['target_type']:
            score += 1.0
        
        return score
    
    def _matches_criteria(self, parsed: Dict, character: str, case: str, char_type: str) -> bool:
        """Check if parsed object matches character criteria"""
        if character:
            # Handle character ambiguities (O/0, I/1, etc.)
            ambiguous_chars = {
                'o': ['0', 'o'],
                '0': ['0', 'o'],
                'i': ['1', 'i'],
                '1': ['1', 'i'],
                'l': ['1', 'l', 'i'],
                's': ['5', 's'],
                '5': ['5', 's'],
                'z': ['2', 'z'],
                '2': ['2', 'z']
            }
            
            target_char = character.lower()
            parsed_char = parsed['character'].lower()
            
            # Check direct match first
            if parsed_char == target_char:
                pass  # Direct match
            # Check ambiguous characters
            elif target_char in ambiguous_chars:
                if parsed_char not in ambiguous_chars[target_char]:
                    return False
            else:
                return False
        
        # For case checking, skip if the parsed object doesn't have case info (like numbers)
        if case and parsed['case'] and parsed['case'] != case:
            return False
        
        # For type checking, be more flexible with ambiguous characters
        if char_type and character:
            target_char = character.lower()
            # If we're looking for ambiguous characters, don't strictly enforce type
            if target_char in ['o', '0', 'i', '1', 'l', 's', '5', 'z', '2']:
                # Allow type flexibility for ambiguous characters
                pass
            elif parsed['type'] != char_type:
                return False
        elif char_type and parsed['type'] != char_type:
            return False
        
        return True

# Example usage
if __name__ == "__main__":
    parser = QuestionParser()
    
    # Test class name parsing
    test_classes = [
        'red_side_K',
        'blue_front_x',
        'green_front_0',
        'grey_side_0',
        'yellow_front_cone'
    ]
    
    print("Class name parsing:")
    for class_name in test_classes:
        parsed = parser.parse_class_name(class_name)
        print(f"{class_name} -> {parsed}")
    
    print("\nQuestion parsing:")
    test_questions = [
        "click the blue uppercase K",
        "click the lowercase h matches the orientation of number 9",
        "click the uppercase F facing sideway",
        "click the number 6 matches the color of number 4"
    ]
    
    for question in test_questions:
        parsed = parser.parse_question(question)
        print(f"{question}")
        print(f"  -> {parsed}")
        print()
