#!/usr/bin/env python3
import pygame
import sys
import os
import argparse
import glob

# Parse arguments to get the image path
parser = argparse.ArgumentParser(description="Photo preview screen")
parser.add_argument(
    "--image", type=str, required=True, help="Path to the image to preview"
)
args = parser.parse_args()

# Initialize pygame
pygame.init()

# Set up fullscreen display
screen_info = pygame.display.Info()
SCREEN_WIDTH = screen_info.current_w
SCREEN_HEIGHT = screen_info.current_h
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)
pygame.display.set_caption("Photo Preview")

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (200, 200, 200)
GREEN = (0, 200, 0)
RED = (255, 0, 0)

# Font setup
font_large = pygame.font.Font(None, 60)
font_medium = pygame.font.Font(None, 48)
font_small = pygame.font.Font(None, 36)


class Button:
    def __init__(self, x, y, w, h, text, action=None, color=GRAY):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.action = action
        self.color = color
        self.hover_color = (
            min(color[0] + 50, 255),
            min(color[1] + 50, 255),
            min(color[2] + 50, 255),
        )
        self.text_color = BLACK if color != RED and color != GREEN else WHITE
        self.font = font_medium
        self.hover = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                if self.action:
                    return self.action
        return None

    def draw(self, screen):
        # Draw button
        color = self.hover_color if self.hover else self.color
        pygame.draw.rect(screen, color, self.rect, 0)
        pygame.draw.rect(screen, BLACK, self.rect, 2)

        # Draw text
        text_surf = self.font.render(self.text, True, self.text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)


def return_result(result):
    """Send result back to parent process and exit"""
    print(f"PREVIEW_RESULT:{result}")
    sys.stdout.flush()
    pygame.quit()
    sys.exit(0)


def find_latest_snapshot():
    """Find the most recent snapshot in the snapshots directory"""
    snapshot_dir = "snapshots"
    snapshot_pattern = os.path.join(snapshot_dir, "snapshot_*.jpg")

    # Get all snapshot files
    snapshot_files = glob.glob(snapshot_pattern)

    if not snapshot_files:
        print("No snapshots found")
        return None

    # Get the most recent snapshot
    latest_snapshot = max(snapshot_files, key=os.path.getctime)
    print(f"Latest snapshot found: {latest_snapshot}")
    return latest_snapshot


def main():
    # Print a message at startup for debugging
    print("Photo preview starting...")
    sys.stdout.flush()

    try:
        # Always find the latest snapshot first
        latest_snapshot = find_latest_snapshot()

        # Determine which image to use
        if latest_snapshot:
            # Use the latest snapshot if available
            image_path = latest_snapshot
            print(f"Using latest snapshot: {image_path}")
        elif os.path.exists(args.image):
            # Fall back to the specified image if no snapshots are found
            image_path = args.image
            print(f"No recent snapshots found. Using specified image: {image_path}")
        else:
            print("ERROR: No image found to preview")
            sys.stdout.flush()
            return 1

        print(f"Using image: {image_path}")
        sys.stdout.flush()

        # Check if image exists
        if not os.path.exists(image_path):
            print(f"ERROR: Image not found: {image_path}")
            sys.stdout.flush()
            return 1

        # Load image
        image = pygame.image.load(image_path)
        img_width, img_height = image.get_size()

        # Scale to fit screen
        scale_factor = min(
            (SCREEN_WIDTH * 0.8) / img_width, (SCREEN_HEIGHT * 0.7) / img_height
        )
        new_width = int(img_width * scale_factor)
        new_height = int(img_height * scale_factor)
        scaled_image = pygame.transform.scale(image, (new_width, new_height))

        # Create buttons
        button_width = 200
        button_height = 60
        try_again_button = Button(
            SCREEN_WIDTH // 2 - button_width - 50,
            SCREEN_HEIGHT - 100,
            button_width,
            button_height,
            "Try Again",
            "try_again",
            RED,
        )
        continue_button = Button(
            SCREEN_WIDTH // 2 + 50,
            SCREEN_HEIGHT - 100,
            button_width,
            button_height,
            "Continue",
            "continue",
            GREEN,
        )

        # Print that we're ready for interaction
        print("Preview screen ready for interaction")
        sys.stdout.flush()

        # Main loop
        running = True
        clock = pygame.time.Clock()
        last_check_time = time.time()

        while running:
            current_time = time.time()

            # Check for newer snapshot every 2 seconds
            if current_time - last_check_time > 2:
                newest_snapshot = find_latest_snapshot()
                if newest_snapshot and newest_snapshot != image_path:
                    print(f"Found newer snapshot: {newest_snapshot}")
                    # Load the new image
                    image_path = newest_snapshot
                    image = pygame.image.load(image_path)
                    img_width, img_height = image.get_size()

                    # Scale to fit screen
                    scale_factor = min(
                        (SCREEN_WIDTH * 0.8) / img_width,
                        (SCREEN_HEIGHT * 0.7) / img_height,
                    )
                    new_width = int(img_width * scale_factor)
                    new_height = int(img_height * scale_factor)
                    scaled_image = pygame.transform.scale(
                        image, (new_width, new_height)
                    )

                last_check_time = current_time

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return_result("try_again")

                # Check button clicks
                action = try_again_button.handle_event(event)
                if action == "try_again":
                    return_result("try_again")

                action = continue_button.handle_event(event)
                if action == "continue":
                    return_result("continue")

            # Draw background
            screen.fill(BLACK)

            # Draw title
            title = font_large.render("Photo Preview", True, WHITE)
            title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 40))
            screen.blit(title, title_rect)

            # Draw image
            image_rect = scaled_image.get_rect(
                center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50)
            )
            screen.blit(scaled_image, image_rect)

            # Draw buttons
            try_again_button.draw(screen)
            continue_button.draw(screen)

            # Draw instructions
            instr_text = font_small.render(
                "Review your photo and decide to keep it or try again", True, WHITE
            )
            instr_rect = instr_text.get_rect(
                center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 160)
            )
            screen.blit(instr_text, instr_rect)

            # Update display
            pygame.display.flip()
            clock.tick(30)

        # If loop exits without a button click
        return_result("try_again")

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.stdout.flush()
        return 1

    finally:
        pygame.quit()

    return 0


if __name__ == "__main__":
    import time  # Add time module import

    sys.exit(main())
