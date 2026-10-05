# Halloween cube icon

Generated with the built-in image-generation tool. The original transparent PNG
is `halloween_cube_icon.png`. Windows executable and installer icons are
`icon.ico` and `normal_icon.ico`, containing 16, 24, 32, 48, 64, 128 and 256 pixel
frames. The game uses the PNG because Pygame does not support PNG-compressed ICO
frames. All assets must be included when rebuilding the packaged game.

Regenerate the Windows icon from the PNG without altering the artwork:

```powershell
.\tools\Convert-PngIcon.ps1 -Source halloween_cube_icon.png -Destination icon.ico
Copy-Item -LiteralPath icon.ico -Destination normal_icon.ico -Force
```

## Generation prompt

Use case: stylized-concept. Asset type: Windows desktop game app icon for The Cube Beta. Primary request: a Halloween cube. Single centered orange pumpkin-shaped CUBE, clearly geometric with three square faces visible in an isometric three-quarter view, subtly beveled edges, a bold carved jack-o-lantern face with glowing amber triangular eyes and a broad playful spooky grin, small dark-green stem on the top. Polished stylized 3D game icon, strong thick silhouette and very simple readable facial shapes that remain recognizable at 32 by 32 pixels. Cube fills about 80 percent of a square canvas, comfortable transparent padding all around. Palette pumpkin orange, warm amber and dark charcoal face cavities. Genuine transparent background with no scenery, floor, background tile or external drop shadow. No text, no letters, no tiny decorative objects, no watermark. One icon only, not an icon sheet.
