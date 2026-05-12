"""
Face Memory Module - Using OpenCV only (no face_recognition library required)
"""
import os
import json
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import hashlib

# Don't import from main - define paths directly
def get_face_memory_dir():
    """Get face memory directory without circular import"""
    # Get the external directory (where config files are stored)
    import sys
    if getattr(sys, "frozen", False):
        ext_dir = Path(sys.executable).parent
    else:
        ext_dir = Path(__file__).resolve().parent.parent  # Go up to main project folder
    
    face_dir = ext_dir / "memory" / "faces"
    face_dir.mkdir(parents=True, exist_ok=True)
    return face_dir

# Define paths without importing from main
FACE_DB_PATH = get_face_memory_dir() / "face_data.json"
KNOWN_FACES_DIR = get_face_memory_dir() / "known_faces"

class FaceMemory:
    def __init__(self):
        self.known_faces = {}  # Store face data by name
        self._load_database()
        
    def _load_database(self):
        """Load saved face data from disk"""
        try:
            if FACE_DB_PATH.exists():
                with open(FACE_DB_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.known_faces = data.get('faces', {})
                print(f"[FaceMemory] ✅ Loaded {len(self.known_faces)} known faces")
            else:
                print("[FaceMemory] 📁 No existing face database, starting fresh")
                self.known_faces = {}
        except Exception as e:
            print(f"[FaceMemory] ⚠️ Failed to load database: {e}")
            self.known_faces = {}
    
    def _save_database(self):
        """Save face data to disk"""
        try:
            data = {
                'faces': self.known_faces,
                'last_updated': datetime.now().isoformat()
            }
            with open(FACE_DB_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"[FaceMemory] 💾 Saved {len(self.known_faces)} faces to database")
        except Exception as e:
            print(f"[FaceMemory] ⚠️ Failed to save database: {e}")
    
    def _get_face_hash(self, face_roi):
        """Generate a hash of face region for unique identification"""
        try:
            # Resize to standard size
            resized = cv2.resize(face_roi, (100, 100))
            # Convert to hash
            return hashlib.md5(resized.tobytes()).hexdigest()
        except:
            return None
    
    def _detect_faces(self, image_path: str) -> List[Tuple]:
        """Detect faces in image using OpenCV"""
        try:
            # Load the image
            image = cv2.imread(str(image_path))
            if image is None:
                return []
            
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Use OpenCV's built-in face detector
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            
            faces = face_cascade.detectMultiScale(
                gray, 
                scaleFactor=1.1, 
                minNeighbors=5, 
                minSize=(50, 50)
            )
            
            return [(x, y, w, h) for (x, y, w, h) in faces]
        except Exception as e:
            print(f"[FaceMemory] Detection error: {e}")
            return []
    
    def _extract_face_features(self, image_path: str, face_location: Tuple) -> np.ndarray:
        """Extract features from a face using histogram of oriented gradients"""
        try:
            image = cv2.imread(str(image_path))
            if image is None:
                return None
            
            x, y, w, h = face_location
            face_roi = image[y:y+h, x:x+w]
            
            # Resize to standard size
            face_resized = cv2.resize(face_roi, (128, 128))
            
            # Convert to HSV color space for better feature extraction
            face_hsv = cv2.cvtColor(face_resized, cv2.COLOR_BGR2HSV)
            
            # Extract color histograms as features
            hist_hue = cv2.calcHist([face_hsv], [0], None, [50], [0, 180])
            hist_sat = cv2.calcHist([face_hsv], [1], None, [50], [0, 256])
            
            # Normalize histograms
            hist_hue = cv2.normalize(hist_hue, hist_hue).flatten()
            hist_sat = cv2.normalize(hist_sat, hist_sat).flatten()
            
            # Combine features
            features = np.concatenate([hist_hue, hist_sat])
            
            return features
            
        except Exception as e:
            print(f"[FaceMemory] Feature extraction error: {e}")
            return None
    
    def _compare_faces(self, features1: np.ndarray, features2: np.ndarray) -> float:
        """Compare two face features and return similarity score (0-1)"""
        if features1 is None or features2 is None:
            return 0
        
        # Use correlation coefficient for comparison
        correlation = np.corrcoef(features1, features2)[0, 1]
        return max(0, correlation if not np.isnan(correlation) else 0)
    
    def learn_face_from_image(self, image_path: str, name: str, relationship: str = "", notes: str = "") -> Dict:
        """
        Learn a new face from an image file
        """
        try:
            # Detect faces
            faces = self._detect_faces(image_path)
            
            if len(faces) == 0:
                return {"success": False, "message": "No face detected in the image, sir."}
            
            if len(faces) > 1:
                return {"success": False, "message": f"I see {len(faces)} faces. Please provide an image with just one face, sir."}
            
            # Extract features from the face
            face_location = faces[0]
            features = self._extract_face_features(image_path, face_location)
            
            if features is None:
                return {"success": False, "message": "Could not extract face features, sir."}
            
            # Check if face already exists (simple comparison)
            for existing_name, existing_data in self.known_faces.items():
                if 'features' in existing_data:
                    similarity = self._compare_faces(features, np.array(existing_data['features']))
                    if similarity > 0.7:  # 70% similarity threshold
                        return {
                            "success": False,
                            "message": f"I already recognize this face as {existing_name} (similarity: {similarity:.2%}), sir."
                        }
            
            # Save face data
            self.known_faces[name] = {
                'features': features.tolist(),
                'relationship': relationship,
                'notes': notes,
                'added_at': datetime.now().isoformat(),
                'image_path': str(image_path),
                'times_seen': 1
            }
            
            # Save a copy of the image
            face_dir = KNOWN_FACES_DIR / name
            face_dir.mkdir(exist_ok=True)
            import shutil
            shutil.copy(image_path, face_dir / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
            
            self._save_database()
            
            return {
                "success": True,
                "message": f"I've learned {name}'s face, sir. {f'Relationship: {relationship}.' if relationship else ''}"
            }
            
        except Exception as e:
            return {"success": False, "message": f"Error learning face: {str(e)}"}
    
    def recognize_face_from_image(self, image_path: str) -> List[Dict]:
        """
        Recognize faces in an image
        """
        results = []
        
        try:
            if len(self.known_faces) == 0:
                return [{"success": False, "message": "I don't know any faces yet, sir. Please teach me first."}]
            
            # Detect faces
            faces = self._detect_faces(image_path)
            
            if len(faces) == 0:
                return [{"success": False, "message": "No faces detected in the image, sir."}]
            
            for i, face_location in enumerate(faces):
                features = self._extract_face_features(image_path, face_location)
                
                if features is None:
                    results.append({"name": "Unknown", "confidence": 0, "relationship": "", "notes": ""})
                    continue
                
                # Compare with known faces
                best_match = None
                best_similarity = 0
                
                for name, data in self.known_faces.items():
                    if 'features' in data:
                        similarity = self._compare_faces(features, np.array(data['features']))
                        if similarity > best_similarity and similarity > 0.5:  # 50% threshold for recognition
                            best_similarity = similarity
                            best_match = name
                
                if best_match:
                    data = self.known_faces[best_match]
                    # Update times seen
                    data['times_seen'] = data.get('times_seen', 0) + 1
                    self._save_database()
                    
                    results.append({
                        "name": best_match,
                        "confidence": best_similarity,
                        "relationship": data.get('relationship', ''),
                        "notes": data.get('notes', ''),
                        "location": face_location
                    })
                else:
                    results.append({
                        "name": "Unknown",
                        "confidence": 0,
                        "relationship": "",
                        "notes": "Face not recognized"
                    })
            
            return results
            
        except Exception as e:
            return [{"success": False, "message": f"Error recognizing faces: {str(e)}"}]
    
    def list_known_faces(self) -> List[Dict]:
        """Return list of all known faces"""
        return [
            {
                "name": name,
                "relationship": data.get("relationship", ""),
                "notes": data.get("notes", ""),
                "added_at": data.get("added_at", ""),
                "times_seen": data.get("times_seen", 0)
            }
            for name, data in self.known_faces.items()
        ]
    
    def delete_face(self, name: str) -> Dict:
        """Delete a face from memory"""
        try:
            if name in self.known_faces:
                del self.known_faces[name]
                self._save_database()
                return {"success": True, "message": f"Removed {name} from my memory, sir."}
            else:
                return {"success": False, "message": f"I don't know anyone named {name}, sir."}
        except Exception as e:
            return {"success": False, "message": f"Error: {str(e)}"}
    
    def update_face_info(self, name: str, relationship: str = None, notes: str = None) -> Dict:
        """Update metadata for a known face"""
        try:
            if name in self.known_faces:
                if relationship:
                    self.known_faces[name]["relationship"] = relationship
                if notes:
                    self.known_faces[name]["notes"] = notes
                self._save_database()
                return {"success": True, "message": f"Updated {name}'s information, sir."}
            else:
                return {"success": False, "message": f"I don't know anyone named {name}, sir."}
        except Exception as e:
            return {"success": False, "message": f"Error: {str(e)}"}

# Global instance
_face_memory_instance = None

def get_face_memory():
    global _face_memory_instance
    if _face_memory_instance is None:
        _face_memory_instance = FaceMemory()
    return _face_memory_instance