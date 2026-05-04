import fitz
import re
import argparse


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("--page", type=int, default=21)
    parser.add_argument("--pdf", type=str, default="gfe_giga_guide.pdf")
    parser.add_argument("--lang", type=str, default="ja")
    args = parser.parse_args()

    doc = fitz.open(args.pdf)
    n = args.page
    page = doc[n]  # 2nd page (0-indexed)

    # Get Japanese text regex
    if args.lang == "ja":
        src_regex = r"[ぁ-ゖァ-ヶ一-鿿]"
    elif args.lang == "ko":
        src_regex = r"[가-힣]"
    else:
        src_regex = r"[a-zA-Z]"

    for b in page.get_text("dict")["blocks"]:
        if b.get("type") == 0:
            # Check if it has Japanese text
            block_text = ""
            for line in b["lines"]:
                for span in line["spans"]:
                    block_text += span["text"]

            if re.search(src_regex, block_text):
                # Draw a red rectangle around valid text blocks
                page.draw_rect(b["bbox"], color=(1, 0, 0), width=1.5)

                # Optionally draw blue rectangles around individual lines
                for line in b["lines"]:
                    page.draw_rect(line["bbox"], color=(0, 0, 1), width=0.5)

    pix = page.get_pixmap(dpi=150)
    import os
    save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "block_visualize")
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    save_path = os.path.join(save_dir, f"page{n}_{args.lang}_visualization.png")
    pix.save(save_path)
    print(f"Saved to {save_path}")


if __name__ == "__main__":
    main()
