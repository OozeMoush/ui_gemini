# Common types for google-genai compatibility

class Part:
    """A part of a Content message containing text"""
    def __init__(self, text: str):
        self.text = text
    
    @classmethod
    def from_text(cls, text: str):
        return cls(text)

class Content:
    """A message content with parts and role"""
    def __init__(self, parts: list, role: str):
        self.parts = parts
        self.role = role
