#!/usr/bin/env python3
"""
สคริปต์สำหรับสร้าง heatmap จากภาพ radar
โดยใช้ฟังก์ชันจากไฟล์ test.py

ตัวอย่างการใช้งาน:
python create_heatmap.py --input radar_image.png --output heatmap_output.png --smooth 10 --gamma 0.8
"""

import os
import argparse
from pathlib import Path
from test import create_radar_heatmap


def main():
    """ฟังก์ชันหลักสำหรับสร้าง heatmap"""
    parser = argparse.ArgumentParser(
        description="สร้าง heatmap จากภาพ radar",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
ตัวอย่างการใช้งาน:
  python create_heatmap.py --input radar_image.png
  python create_heatmap.py --input radar_image.png --output custom_output.png
  python create_heatmap.py --input radar_image.png --smooth 10 --gamma 0.8 --green-only
  python create_heatmap.py --input folder/*.png --batch
        """
    )
    
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path ของไฟล์ภาพ input (รองรับ wildcard สำหรับ --batch)"
    )
    
    parser.add_argument(
        "--output", "-o",
        help="Path ของไฟล์ output (ถ้าไม่ระบุจะเป็น input_heatmap.png)"
    )
    
    parser.add_argument(
        "--smooth", "-s",
        type=int,
        default=8,
        help="ความ smooth ของภาพ (default: 8)"
    )
    
    parser.add_argument(
        "--gamma", "-g",
        type=float,
        default=0.80,
        help="การปรับแสง (default: 0.80)"
    )
    
    parser.add_argument(
        "--low-cut", "-l",
        type=float,
        default=0.12,
        help="จุดตัดต่ำ (default: 0.12)"
    )
    
    parser.add_argument(
        "--feather", "-f",
        type=float,
        default=0.10,
        help="ความนุ่มของขอบ (default: 0.10)"
    )
    
    parser.add_argument(
        "--green-only",
        action="store_true",
        help="ใช้สีเขียวอย่างเดียว"
    )
    
    parser.add_argument(
        "--batch",
        action="store_true",
        help="ประมวลผลหลายไฟล์พร้อมกัน (ใช้กับ wildcard ใน --input)"
    )
    
    args = parser.parse_args()
    
    if args.batch:
        # โหมด batch processing
        import glob
        input_files = glob.glob(args.input)
        
        if not input_files:
            print(f"ไม่พบไฟล์ที่ตรงกับ pattern: {args.input}")
            return
            
        print(f"พบไฟล์ {len(input_files)} ไฟล์ สำหรับประมวลผล")
        success_count = 0
        
        for input_file in input_files:
            print(f"\nประมวลผล: {input_file}")
            
            # สร้าง output path สำหรับแต่ละไฟล์
            input_path = Path(input_file)
            output_path = input_path.parent / f"{input_path.stem}_heatmap{input_path.suffix}"
            
            result = create_radar_heatmap(
                input_path=input_file,
                output_path=str(output_path),
                smooth_px=args.smooth,
                gamma=args.gamma,
                low_cut=args.low_cut,
                feather=args.feather,
                use_green_only=args.green_only
            )
            
            if result:
                success_count += 1
                
        print(f"\n[สำเร็จ] ประมวลผลเสร็จสิ้น: {success_count}/{len(input_files)} ไฟล์")
        
    else:
        # โหมดไฟล์เดียว
        if not os.path.exists(args.input):
            print(f"ไม่พบไฟล์: {args.input}")
            return
            
        result = create_radar_heatmap(
            input_path=args.input,
            output_path=args.output,
            smooth_px=args.smooth,
            gamma=args.gamma,
            low_cut=args.low_cut,
            feather=args.feather,
            use_green_only=args.green_only
        )
        
        if result:
            print(f"[สำเร็จ] สร้าง heatmap เสร็จสิ้น: {result}")
        else:
            print("[ผิดพลาด] ไม่สามารถสร้าง heatmap ได้")


if __name__ == "__main__":
    main()
