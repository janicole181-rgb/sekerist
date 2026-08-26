#!/usr/bin/env python3
"""
API Image Solver (Pure ONNX) - Processes images using ONNX Runtime without PyTorch dependency
"""

import io
import os

# Load .env file if it exists
def load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip().strip("'\"")
        except Exception:
            pass

load_env()

# Suppress ONNX Runtime warnings about missing TensorRT
os.environ.setdefault('ORT_LOGGING_LEVEL', '3')  # Error level only
os.environ.setdefault('ORT_DISABLE_THREAD_AFFINITY', '1')
import time
import base64
import requests
from typing import Dict, List, Optional, Tuple, Union
from PIL import Image
import cv2
import numpy as np
# Add PyTorch's CUDA DLLs to the search path so onnxruntime-gpu can find
# cublas64_12.dll, cudnn64_9.dll, etc. (they ship with torch on Windows)
try:
    import torch as _torch
    _torch_lib = os.path.join(os.path.dirname(_torch.__file__), 'lib')
    if os.path.isdir(_torch_lib):
        os.add_dll_directory(_torch_lib)
except Exception:
    pass

import onnxruntime as ort
from improved_question_parser import ImprovedQuestionParser
from urllib.parse import urlparse

class APIImageSolverONNX:
    """
    Solves CAPTCHA images using pure ONNX Runtime (no PyTorch dependency)
    """
    
    def __init__(self, model_path: str = "yidun-yolov8n-cpu-int8.onnx", use_gpu: bool = False,
                 use_fp16: bool = False, use_int8: bool = True,
                 intra_op_num_threads: int = 0, inter_op_num_threads: int = 1):
        self.model_path = model_path
        self.use_gpu = False
        self.use_fp16 = False
        self.use_int8 = True
        self.parser = ImprovedQuestionParser()

        # Threading config — 0 means "let ORT decide" (uses all logical cores)
        cpu_count = os.cpu_count() or 4
        self._intra_threads = intra_op_num_threads if intra_op_num_threads > 0 else min(cpu_count, 4)
        self._inter_threads = inter_op_num_threads if inter_op_num_threads > 0 else 1

        # Verify model exists locally or fallback to packaged file
        if not os.path.exists(self.model_path):
            dir_model = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yidun-yolov8n-cpu-int8.onnx")
            if os.path.exists(dir_model):
                self.model_path = dir_model

        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"INT8 CPU Model not found at {self.model_path}")

        self.gpu_available = False
        self.device = 'cpu'
        print(f"✅ CPU mode enabled (YOLOv8n INT8 CPU Solver) [intra={self._intra_threads} inter={self._inter_threads}]")

        # Load ONNX model
        self._load_model()

        # Disable FP16 if we're using CPU provider (FP16 only works well on GPU)
        actual_provider = self.session.get_providers()[0]
        if actual_provider == 'CPUExecutionProvider' and self.use_fp16:
            print(f"⚠️  FP16 disabled (CPU doesn't support FP16 efficiently)")
            self.use_fp16 = False

        # Get model metadata
        self._get_model_info()
    
    def _check_gpu_availability(self) -> bool:
        """
        Check if GPU (CUDA) is available for ONNX Runtime
        
        Returns:
            True if GPU is available, False otherwise
        """
        try:
            providers = ort.get_available_providers()
            # Only check for CUDA provider (TensorRT requires additional dependencies)
            return 'CUDAExecutionProvider' in providers
        except Exception:
            return False
    
    def _load_model(self):
        """Load ONNX model with execution provider and session options tuned for the target device."""
        providers = []

        if self.device == 'cuda':
            available_providers = ort.get_available_providers()
            if 'CUDAExecutionProvider' in available_providers:
                providers.append('CUDAExecutionProvider')

        # CPU is always the fallback
        providers.append('CPUExecutionProvider')

        try:
            sess_options = ort.SessionOptions()
            sess_options.log_severity_level = 3   # ERROR only (suppress info/warnings)

            # ── Graph optimization (applies for both GPU & CPU) ───────────────
            # ENABLE_ALL folds constants, eliminates dead nodes, fuses Conv+BN+ReLU.
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            if self.device == 'cpu':
                # ── Thread tuning: use caller-supplied values (set by config.json) ──
                # intra_op: parallelism within a single op (e.g. matmul rows)
                # inter_op: parallelism between sequential independent ops
                # Both default to min(cpu_count, 4) and 1 respectively when not
                # overridden, giving a good balance on 4–12 core VPS machines.
                sess_options.intra_op_num_threads = self._intra_threads
                sess_options.inter_op_num_threads = self._inter_threads
                sess_options.execution_mode       = ort.ExecutionMode.ORT_SEQUENTIAL

                # ── Memory optimizations ──────────────────────────────────────
                sess_options.enable_mem_pattern   = True
                sess_options.enable_cpu_mem_arena = True

            self.session = ort.InferenceSession(
                self.model_path,
                sess_options=sess_options,
                providers=providers,
            )
            actual_provider = self.session.get_providers()[0]
            print(f"Model loaded: {actual_provider}  [{self.model_path}] "
                  f"[intra={self._intra_threads} inter={self._inter_threads}]")
        except Exception as e:
            raise RuntimeError(f"Failed to load ONNX model: {str(e)}")

    
    def _get_model_info(self):
        """Extract model metadata from ONNX session"""
        # Get input info
        self.input_name = self.session.get_inputs()[0].name
        self.input_shape = self.session.get_inputs()[0].shape
        
        # Get output names
        self.output_names = [output.name for output in self.session.get_outputs()]
        
        # YOLOv8 typically has 1 output for detection
        print(f"📊 Model info:")
        print(f"   Input: {self.input_name} {self.input_shape}")
        print(f"   Outputs: {len(self.output_names)} ({', '.join(self.output_names)})")
        
        # Parse class names from model metadata if available
        self.class_names = self._parse_class_names()
        if self.class_names:
            print(f"📊 Loaded {len(self.class_names)} class names from model metadata")
        else:
            print(f"⚠️  No class names found in metadata, using generic names")
    
    def _parse_class_names(self) -> Dict[int, str]:
        """
        Parse class names from model metadata, with fallback to class_mapping.json.
        
        Some models (yidun-yolov8n/s) are exported without proper class name metadata
        and only have generic 'class_0', 'class_1' names. In that case we load the
        authoritative class_mapping.json from the model directory.
        
        Returns:
            Dictionary mapping class IDs to names
        """
        import json
        import ast

        names_dict = {}
        try:
            metadata = self.session.get_modelmeta()
            custom_metadata = metadata.custom_metadata_map
            
            # YOLOv8 ONNX models store class names in 'names' metadata
            if 'names' in custom_metadata:
                names_str = custom_metadata['names']
                
                for parser in [
                    lambda s: json.loads(s),
                    lambda s: ast.literal_eval(s),
                    lambda s: json.loads(s.replace("'", '"')),
                ]:
                    try:
                        parsed = parser(names_str)
                        if isinstance(parsed, dict):
                            names_dict = {int(k): v for k, v in parsed.items()}
                            break
                    except Exception:
                        continue
            
            if not names_dict:
                # Fallback: check other metadata keys
                for key in custom_metadata:
                    if 'name' in key.lower() or 'class' in key.lower():
                        try:
                            parsed = json.loads(custom_metadata[key])
                            if isinstance(parsed, dict):
                                names_dict = {int(k): v for k, v in parsed.items()}
                                break
                        except Exception:
                            try:
                                parsed = ast.literal_eval(custom_metadata[key])
                                if isinstance(parsed, dict):
                                    names_dict = {int(k): v for k, v in parsed.items()}
                                    break
                            except Exception:
                                continue

        except Exception as e:
            print(f"⚠️  Warning: Could not extract class names from model metadata: {e}")
        
        # Detect generic placeholder names (exported without real labels)
        # e.g. all values are 'class_0', 'class_1', ... — unusable for matching
        def _is_generic(d: dict) -> bool:
            if not d:
                return True
            sample = list(d.values())[:10]
            return all(str(v).startswith('class_') for v in sample)

        if _is_generic(names_dict):
            # Try class_mapping.json next to the model file, then in CWD
            mapping_candidates = [
                os.path.join(os.path.dirname(os.path.abspath(self.model_path)), 'class_mapping.json'),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), 'class_mapping.json'),
                'class_mapping.json',
            ]
            for mapping_path in mapping_candidates:
                if os.path.exists(mapping_path):
                    try:
                        with open(mapping_path, 'r', encoding='utf-8') as f:
                            raw = json.load(f)
                        names_dict = {int(k): v for k, v in raw.items()}
                        print(f"📋 Loaded {len(names_dict)} class names from {mapping_path}")
                        break
                    except Exception as e:
                        print(f"⚠️  Failed to load {mapping_path}: {e}")
        
        return names_dict
    
    def get_device_info(self) -> Dict[str, str]:
        """
        Get information about the current device being used
        
        Returns:
            Dictionary with device information
        """
        info = {
            'device': self.device,
            'gpu_available': self.gpu_available,
            'gpu_requested': self.use_gpu,
            'fp16_enabled': self.use_fp16,
            'int8_enabled': self.use_int8,
            'model_path': self.model_path,
            'execution_provider': self.session.get_providers()[0]
        }
        
        return info
    
    def _preprocess_image(self, cv2_image: np.ndarray) -> Tuple[np.ndarray, float, Tuple[int, int]]:
        """
        Preprocess image for YOLO inference
        
        Args:
            cv2_image: OpenCV image (BGR format)
            
        Returns:
            Tuple of (preprocessed_image, scale_factor, original_shape)
        """
        # Get original shape
        orig_height, orig_width = cv2_image.shape[:2]
        
        # High-accuracy Contrast Enhancement (CLAHE) for robust color matching
        try:
            yuv = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2YUV)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            yuv[:,:,0] = clahe.apply(yuv[:,:,0])
            cv2_image = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)
        except Exception:
            pass
        
        # YOLOv8 typically uses 640x640 input
        # Get input shape from model (batch, channels, height, width)
        if isinstance(self.input_shape[2], int):
            target_height = self.input_shape[2]
            target_width = self.input_shape[3]
        else:
            # Dynamic shape, use default
            target_height = target_width = 640
        
        # Letterbox resize (maintain aspect ratio)
        scale = min(target_width / orig_width, target_height / orig_height)
        new_width = int(orig_width * scale)
        new_height = int(orig_height * scale)
        
        # Resize image
        resized = cv2.resize(cv2_image, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
        
        # Create padded image
        padded = np.full((target_height, target_width, 3), 114, dtype=np.uint8)
        
        # Calculate padding offsets
        pad_x = (target_width - new_width) // 2
        pad_y = (target_height - new_height) // 2
        
        # Place resized image on padded canvas
        padded[pad_y:pad_y+new_height, pad_x:pad_x+new_width] = resized
        
        # Convert BGR to RGB
        rgb_image = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
        
        # Normalize to [0, 1] and transpose to (C, H, W)
        input_image = rgb_image.astype(np.float32) / 255.0
        input_image = np.transpose(input_image, (2, 0, 1))
        
        # Add batch dimension (1, C, H, W)
        input_image = np.expand_dims(input_image, axis=0)
        
        # Convert to FP16 if enabled
        if self.use_fp16:
            input_image = input_image.astype(np.float16)
        
        # Return padding info for coordinate conversion
        return input_image, scale, (orig_height, orig_width), (pad_x, pad_y)
    
    def _postprocess_output(self, output: np.ndarray, scale: float, 
                           orig_shape: Tuple[int, int],
                           padding: Tuple[int, int],
                           conf_threshold: float = 0.25,
                           iou_threshold: float = 0.45) -> List[Dict]:
        """
        Postprocess YOLO output to get detections
        
        Args:
            output: Raw model output
            scale: Scale factor from preprocessing
            orig_shape: Original image shape (height, width)
            padding: Padding offsets (pad_x, pad_y) from letterbox resize
            conf_threshold: Confidence threshold
            iou_threshold: IoU threshold for NMS
            
        Returns:
            List of detection dictionaries
        """
        # YOLOv8 output shape: (1, 84, 8400) or (1, num_classes+4, num_predictions)
        # Format: [x_center, y_center, width, height, class_0_conf, class_1_conf, ...]
        
        output = output[0]  # Remove batch dimension
        
        # Transpose to (num_predictions, 84)
        if output.shape[0] < output.shape[1]:
            output = output.transpose()
        
        # Extract boxes and scores
        boxes = output[:, :4]  # x_center, y_center, width, height
        scores = output[:, 4:]  # class confidences
        
        # Get class with highest confidence for each prediction
        class_ids = np.argmax(scores, axis=1)
        confidences = np.max(scores, axis=1)
        
        # Filter by confidence threshold
        mask = confidences > conf_threshold
        boxes = boxes[mask]
        confidences = confidences[mask]
        class_ids = class_ids[mask]
        
        if len(boxes) == 0:
            return []
        
        # Convert from center format to corner format (x1, y1, x2, y2)
        x_center, y_center, width, height = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
        x1 = x_center - width / 2
        y1 = y_center - height / 2
        x2 = x_center + width / 2
        y2 = y_center + height / 2
        
        # Remove padding offset then scale back to original image size
        pad_x, pad_y = padding
        x1 = (x1 - pad_x) / scale
        y1 = (y1 - pad_y) / scale
        x2 = (x2 - pad_x) / scale
        y2 = (y2 - pad_y) / scale
        
        # Apply NMS
        indices = self._nms(
            np.stack([x1, y1, x2, y2], axis=1),
            confidences,
            iou_threshold
        )
        
        # Build detection list
        detections = []
        for idx in indices:
            x1_val, y1_val, x2_val, y2_val = x1[idx], y1[idx], x2[idx], y2[idx]
            width_val = x2_val - x1_val
            height_val = y2_val - y1_val
            
            # Get class name
            cls_id = int(class_ids[idx])
            class_name = self.class_names.get(cls_id, f"class_{cls_id}")
            
            detection_info = {
                'class_id': cls_id,
                'class_name': class_name,
                'confidence': float(confidences[idx]),
                'bounding_box': {
                    'x1': float(x1_val),
                    'y1': float(y1_val),
                    'x2': float(x2_val),
                    'y2': float(y2_val),
                    'width': float(width_val),
                    'height': float(height_val)
                }
            }
            
            detections.append(detection_info)
        
        return detections
    
    def _nms(self, boxes: np.ndarray, scores: np.ndarray, iou_threshold: float) -> List[int]:
        """
        Non-Maximum Suppression
        
        Args:
            boxes: Array of boxes in format [x1, y1, x2, y2]
            scores: Array of confidence scores
            iou_threshold: IoU threshold for suppression
            
        Returns:
            List of indices to keep
        """
        x1 = boxes[:, 0]
        y1 = boxes[:, 1]
        x2 = boxes[:, 2]
        y2 = boxes[:, 3]
        
        areas = (x2 - x1) * (y2 - y1)
        order = scores.argsort()[::-1]
        
        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(i)
            
            if order.size == 1:
                break
            
            # Compute IoU
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            
            w = np.maximum(0.0, xx2 - xx1)
            h = np.maximum(0.0, yy2 - yy1)
            inter = w * h
            
            iou = inter / (areas[i] + areas[order[1:]] - inter)
            
            inds = np.where(iou <= iou_threshold)[0]
            order = order[inds + 1]
        
        return keep
    
    def _bytes_to_cv2_image(self, image_bytes: bytes) -> np.ndarray:
        """
        Convert bytes to OpenCV image format
        
        Args:
            image_bytes: Raw image bytes
            
        Returns:
            OpenCV image array
        """
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img
    
    def _base64_to_cv2_image(self, base64_string: str) -> np.ndarray:
        """
        Convert base64 string to OpenCV image format
        
        Args:
            base64_string: Base64 encoded image string
            
        Returns:
            OpenCV image array
        """
        if base64_string.startswith('data:image'):
            base64_string = base64_string.split(',')[1]
        
        image_bytes = base64.b64decode(base64_string)
        return self._bytes_to_cv2_image(image_bytes)
    
    def _pil_to_cv2_image(self, pil_image: Image.Image) -> np.ndarray:
        """
        Convert PIL Image to OpenCV image format
        
        Args:
            pil_image: PIL Image object
            
        Returns:
            OpenCV image array
        """
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')
        
        img_array = np.array(pil_image)
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        return img_bgr
    
    def _is_url(self, string: str) -> bool:
        """
        Check if a string is a valid URL
        
        Args:
            string: String to check
            
        Returns:
            True if string is a URL, False otherwise
        """
        try:
            result = urlparse(string)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def _download_image_from_url(self, url: str) -> bytes:
        """
        Download image from URL and return as bytes
        
        Args:
            url: Image URL
            
        Returns:
            Image bytes
        """
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.content
        except Exception as e:
            raise ValueError(f"Failed to download image from URL {url}: {str(e)}")
    
    def _process_image_input(self, image_input: Union[bytes, str, Image.Image]) -> np.ndarray:
        """
        Process various image input types to OpenCV format
        
        Args:
            image_input: Can be bytes, base64 string, URL string, or PIL Image
            
        Returns:
            OpenCV image array
        """
        if isinstance(image_input, bytes):
            return self._bytes_to_cv2_image(image_input)
        elif isinstance(image_input, str):
            if self._is_url(image_input):
                image_bytes = self._download_image_from_url(image_input)
                return self._bytes_to_cv2_image(image_bytes)
            else:
                return self._base64_to_cv2_image(image_input)
        elif isinstance(image_input, Image.Image):
            return self._pil_to_cv2_image(image_input)
        else:
            raise ValueError(f"Unsupported image input type: {type(image_input)}")
    
    def _cv2_to_bytes(self, cv2_image: np.ndarray, format: str = 'PNG') -> bytes:
        """
        Convert OpenCV image to bytes
        
        Args:
            cv2_image: OpenCV image array
            format: Output format ('PNG', 'JPEG', etc.)
            
        Returns:
            Image as bytes
        """
        success, encoded_img = cv2.imencode(f'.{format.lower()}', cv2_image)
        if not success:
            raise ValueError(f"Failed to encode image to {format}")
        
        return encoded_img.tobytes()
    
    def get_detections_from_image(self, image_input: Union[bytes, str, Image.Image], 
                                 conf_threshold: float = 0.25, 
                                 iou_threshold: float = 0.45) -> List[Dict]:
        """
        Get detections from image input without saving to disk
        
        Args:
            image_input: Image as bytes, base64 string, URL string, or PIL Image
            conf_threshold: Confidence threshold for detection
            iou_threshold: IoU threshold for NMS
            
        Returns:
            List of detection dictionaries
        """
        # Convert image input to OpenCV format
        cv2_image = self._process_image_input(image_input)
        
        if cv2_image is None:
            raise ValueError("Failed to process image input")
        
        # Preprocess image
        input_tensor, scale, orig_shape, padding = self._preprocess_image(cv2_image)
        
        # Run inference
        outputs = self.session.run(
            self.output_names,
            {self.input_name: input_tensor}
        )
        
        # Postprocess output
        detections = self._postprocess_output(
            outputs[0],
            scale,
            orig_shape,
            padding,
            conf_threshold,
            iou_threshold
        )
        
        return detections
    
    def solve_captcha_from_api(self, resp_get: Dict, 
                               conf_threshold: float = 0.18, 
                               iou_threshold: float = 0.50) -> Dict:
        """
        Solve CAPTCHA from API response data
        
        Args:
            resp_get: API response dictionary containing 'data' with 'front' (question) and 'bg' (background images)
            conf_threshold: Confidence threshold for detection
            iou_threshold: IoU threshold for NMS
            
        Returns:
            Dictionary containing solution information
        """
        start_time = time.time()
        
        try:
            # Extract question and background image from API response
            try:
                question = resp_get['data']['front']
                background_images = resp_get['data']['bg']
            except:
                question = resp_get['front']
                background_images = resp_get['bg']
            
            # Use the first background image (index 0 as specified)
            if not background_images:
                return {
                    'success': False,
                    'error': 'No background images found in API response',
                    'processing_time': time.time() - start_time
                }
            
            img_data = background_images[0]
            
            # Clean the question using improved parser
            cleaned_question = self.parser.preprocess_question(question)
            
            # Get detections from the image
            detections = self.get_detections_from_image(
                img_data, 
                conf_threshold, 
                iou_threshold
            )
            
            if not detections:
                return {
                    'success': False,
                    'error': 'No detections found in image',
                    'question': question,
                    'cleaned_question': cleaned_question,
                    'processing_time': time.time() - start_time
                }
            
            # Parse the question using improved parser
            parsed_question = self.parser.parse_question(question)
            
            # Find the target detection
            target_detection = self.parser.find_target(cleaned_question, detections)
            
            processing_time = time.time() - start_time
            
            if target_detection is None:
                return {
                    'success': False,
                    'error': 'No matching target found',
                    'question': question,
                    'cleaned_question': cleaned_question,
                    'parsed_question': parsed_question,
                    'processing_time': processing_time,
                    'available_detections': [
                        {
                            'class_name': det['class_name'],
                            'confidence': det['confidence'],
                            'parsed': self.parser.parse_class_name(det['class_name'])
                        } for det in detections
                    ]
                }
            
            # Calculate click coordinates (center of bounding box)
            bbox = target_detection['bounding_box']
            click_x = (bbox['x1'] + bbox['x2']) / 2
            click_y = (bbox['y1'] + bbox['y2']) / 2
            
            return {
                'success': True,
                'question': question,
                'cleaned_question': cleaned_question,
                'parsed_question': parsed_question,
                'target_detection': target_detection,
                'processing_time': processing_time,
                'click_coordinates': {
                    'x': click_x,
                    'y': click_y
                },
                'solution_summary': {
                    'class_name': target_detection['class_name'],
                    'confidence': target_detection['confidence'],
                    'parsed': self.parser.parse_class_name(target_detection['class_name']),
                    'bounding_box': bbox
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Exception during processing: {str(e)}',
                'question': resp_get.get('data', {}).get('front', 'Unknown'),
                'processing_time': time.time() - start_time
            }
    
    def solve_captcha_from_bytes(self, question: str, img_bytes: bytes,
                                conf_threshold: float = 0.18, 
                                iou_threshold: float = 0.50) -> Dict:
        """
        Solve CAPTCHA from question string and image bytes
        
        Args:
            question: The question text
            img_bytes: Image as bytes
            conf_threshold: Confidence threshold for detection
            iou_threshold: IoU threshold for NMS
            
        Returns:
            Dictionary containing solution information
        """
        start_time = time.time()
        
        try:
            # Clean the question using improved parser
            cleaned_question = self.parser.preprocess_question(question)
            
            # Get detections from the image
            detections = self.get_detections_from_image(
                img_bytes, 
                conf_threshold, 
                iou_threshold
            )
            
            if not detections:
                return {
                    'success': False,
                    'error': 'No detections found in image',
                    'question': question,
                    'cleaned_question': cleaned_question,
                    'processing_time': time.time() - start_time
                }
            
            # Parse the question using improved parser
            parsed_question = self.parser.parse_question(question)
            
            # Find the target detection
            target_detection = self.parser.find_target(cleaned_question, detections)
            
            processing_time = time.time() - start_time
            
            if target_detection is None:
                return {
                    'success': False,
                    'error': 'No matching target found',
                    'question': question,
                    'cleaned_question': cleaned_question,
                    'parsed_question': parsed_question,
                    'processing_time': processing_time,
                    'available_detections': [
                        {
                            'class_name': det['class_name'],
                            'confidence': det['confidence'],
                            'parsed': self.parser.parse_class_name(det['class_name'])
                        } for det in detections
                    ]
                }
            
            # Calculate click coordinates (center of bounding box)
            bbox = target_detection['bounding_box']
            click_x = (bbox['x1'] + bbox['x2']) / 2
            click_y = (bbox['y1'] + bbox['y2']) / 2
            
            return {
                'success': True,
                'question': question,
                'cleaned_question': cleaned_question,
                'parsed_question': parsed_question,
                'target_detection': target_detection,
                'processing_time': processing_time,
                'click_coordinates': {
                    'x': click_x,
                    'y': click_y
                },
                'solution_summary': {
                    'class_name': target_detection['class_name'],
                    'confidence': target_detection['confidence'],
                    'parsed': self.parser.parse_class_name(target_detection['class_name']),
                    'bounding_box': bbox
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Exception during processing: {str(e)}',
                'question': question,
                'processing_time': time.time() - start_time
            }
    
    def create_visual_result(self, image_input: Union[bytes, str, Image.Image], 
                           result: Dict, output_format: str = 'PNG') -> bytes:
        """
        Create visual result with bounding boxes and annotations
        
        Args:
            image_input: Original image input
            result: Result dictionary from solve_captcha_*
            output_format: Output format ('PNG', 'JPEG', etc.)
            
        Returns:
            Annotated image as bytes
        """
        if not result['success']:
            raise ValueError("Cannot create visual result for failed solution")
        
        # Convert image input to OpenCV format
        cv2_image = self._process_image_input(image_input)
        
        # Draw bounding box
        bbox = result['target_detection']['bounding_box']
        cv2.rectangle(cv2_image, 
                     (int(bbox['x1']), int(bbox['y1'])), 
                     (int(bbox['x2']), int(bbox['y2'])), 
                     (0, 255, 0), 2)
        
        # Draw click point
        click_x = int(result['click_coordinates']['x'])
        click_y = int(result['click_coordinates']['y'])
        cv2.circle(cv2_image, (click_x, click_y), 5, (0, 0, 255), -1)
        
        # Add text annotations
        class_name = result['solution_summary']['class_name']
        confidence = result['solution_summary']['confidence']
        
        # Add class name and confidence
        cv2.putText(cv2_image, f"{class_name} ({confidence:.3f})", 
                   (int(bbox['x1']), int(bbox['y1'] - 10)), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        # Add question (truncated if too long)
        question = result['cleaned_question'][:50] + "..." if len(result['cleaned_question']) > 50 else result['cleaned_question']
        cv2.putText(cv2_image, question, 
                   (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Convert back to bytes
        return self._cv2_to_bytes(cv2_image, output_format)


def main():
    """Example usage of the ONNX API Image Solver"""
    print("API Image Solver (Pure ONNX) - Example Usage")
    print("=" * 50)
    
    try:
        # Initialize solver
        solver = APIImageSolverONNX()
        
        # Show device info
        device_info = solver.get_device_info()
        print(f"\n📊 Device Information:")
        for key, value in device_info.items():
            print(f"   {key}: {value}")
        
        print("\nExample 1: Simulated API response")
        print("To use this solver, pass the actual API response to solve_captcha_from_api()")
        
        print("\nExample 2: Direct usage with image bytes")
        print("question = 'Click on the red letter A'")
        print("img_bytes = resp_get['data']['bg'][0]")
        print("result = solver.solve_captcha_from_bytes(question, img_bytes)")
        
        print("\nThe solver returns a dictionary with:")
        print("- success: Boolean indicating if solution was found")
        print("- click_coordinates: {x, y} coordinates to click")
        print("- solution_summary: Information about the detected target")
        print("- processing_time: Time taken to process")
        
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
