import pygame
import sys
import os

# Initialize pygame
pygame.init()

# Get screen info for fullscreen
screen_info = pygame.display.Info()
SCREEN_WIDTH = screen_info.current_w
SCREEN_HEIGHT = screen_info.current_h

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

# Fullscreen display
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)
pygame.display.set_caption("Photobooth")

# Font setup
font_path = pygame.font.get_default_font()  # Default font
try:
    # Try to use a nicer font if available
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    if not os.path.exists(font_path):
        font_path = pygame.font.get_default_font()
except:
    pass

# Create fonts of different sizes
large_font = pygame.font.Font(font_path, 120)
small_font = pygame.font.Font(font_path, 40)

def main():
    clock = pygame.time.Clock()
    running = True
    
    # Main loop
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
        
        # Clear screen
        screen.fill(BLACK)
        
        # Render "PHOTOBOOTH" text
        title_text = large_font.render("PHOTOBOOTH", True, WHITE)
        title_rect = title_text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 50))
        screen.blit(title_text, title_rect)
        
        # Render instruction text
        instr_text = small_font.render("Stand in front of the camera to begin", True, WHITE)
        instr_rect = instr_text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 + 100))
        screen.blit(instr_text, instr_rect)
        
        # Update display
        pygame.display.flip()
        clock.tick(30)
    
    # Clean up
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()

