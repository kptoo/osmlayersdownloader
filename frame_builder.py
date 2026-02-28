class FrameBuilder:
    def __init__(self, width, height, depth):
        self.width = width
        self.height = height
        self.depth = depth

    def calculate_volume(self):
        """Calculate the volume of the frame."""
        return self.width * self.height * self.depth

    def create_geometry(self):
        """Generate a representation of the frame's geometry."""
        return {
            'width': self.width,
            'height': self.height,
            'depth': self.depth,
            'volume': self.calculate_volume()
        }
