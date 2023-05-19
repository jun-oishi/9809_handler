# coding: utf-8

import numpy as np
import re


def strArr2ndarray(strArr: list[str]) -> np.ndarray:
    splitted = []
    for s in strArr:
        splitted.append(s.split())
    return np.array(splitted, dtype=np.float64)


class Block:
    def __init__(
        self, ini_energy: float, fin_energy: float, step: float, time: float, num: int
    ):
        self.ini_energy = ini_energy
        self.fin_energy = fin_energy
        self.step = step
        self.time = time
        self.num = num
        return

    def matchWith(self, other: "Block") -> bool:
        ret = (
            self.ini_energy == other.ini_energy
            and self.fin_energy == other.fin_energy
            and self.step == other.step
        )
        return ret


class Blocks:
    def __init__(self, blocks: list[Block] = []):
        self.__blocks = blocks.copy()
        return

    def __getitem__(self, key):
        return self.__blocks[key]

    def __setitem__(self, key, value):
        self.__blocks[key] = value
        return

    def __len__(self):
        return len(self.__blocks)

    def append(self, block: Block):
        self.__blocks.append(block)
        return

    def lines(self):
        lines = []
        header = " Block       Init-Eng Final-Eng      Step/eV     Time/s       Num\n"
        lines.append(header)
        for i, block in enumerate(self.__blocks):
            lines.append(
                f"    {i+1:>2}"
                + f" {block.ini_energy:>14.2f}"
                + f" {block.fin_energy:>9.2f}"
                + f" {block.step:>12.2f}"
                + f" {block.time:>10.2f}"
                + f" {block.num:>10}"
                + "\n"
            )
        return lines

    def matchWith(self, other: "Blocks") -> bool:
        if len(self) != len(other):
            return False
        for b1, b2 in zip(self.__blocks, other.__blocks):
            if not b1.matchWith(b2):
                return False
        return True


class File:
    """
    9809 file handler

    Attributes
    ----------
    facility : str
    beamline : str
    filanem : str
    start_datetime : str
    end_datetime : str
    comment : str
    ring : str
    mono : str  // 分光器の情報
    blocks : Blocks // 測定エネルギ刻みの情報
    data_headers : list[list[str]] // データのヘッダー
    """

    MEASUERMENT_MODE = {
        2: "Transmission",
    }
    ENERGY_AXIS = {1: "other", 2: "angle"}

    def __init__(self, path):
        with open(path, "r") as f:
            lines = f.readlines()
        if not lines[0].strip().startswith("9809"):
            raise Exception("Invalid file: not 9809")
        self.tag = lines[1].strip()

        # 1行目 : `9809 施設名 ビームライン名`
        words = re.split(" +", lines[0].strip())
        self.facility = words[1]
        self.beamline = words[2]
        # 2行目 : `ファイル名 開始日 時刻 - 終了日 時刻`
        words = re.split(" +", lines[1].strip())
        self.filename = words[0]
        self.start_datetime = words[1] + " " + words[2]
        self.end_datetime = words[4] + " " + words[5]
        # 3行目 : `コメント`
        self.comment = lines[2].strip()
        # 4行目 : `リング電流`
        self.ring = lines[3].strip()
        # 5行目 : `分光器の情報`
        self.mono = lines[4].strip()
        # 6行目 : `測定モード`
        line = lines[5].strip()
        if match := re.search(r"\(( +)([0-9]+)\)", line):
            self.mode = int(match.group(2))
        if match := re.search(r"Repetition=( +)([0-9]+)", line):
            self.repetition = int(match.group(2))
        if match := re.search(r"Points=( +)([0-9]+)", line):
            self.points = int(match.group(2))
        # 7行目 : ``
        line = lines[6].strip()
        n_blocks = 0
        if match := re.search(r"energy axis\(([12])\)", line):
            self.energy_axis = int(match.group(1))
        if match := re.search(r"Block =( +)([0-9]+)", line):
            n_blocks = int(match.group(2))

        self.blocks = Blocks()
        block_end = 8 + n_blocks
        for line in lines[9 : block_end + 1]:
            words = line.split()
            self.blocks.append(
                Block(
                    float(words[1]),
                    float(words[2]),
                    float(words[3]),
                    float(words[4]),
                    int(words[5]),
                )
            )

        data_header_start = block_end + 2
        num_headers = 0
        for i, line in enumerate(lines[data_header_start:]):
            try:
                float(line.strip().split()[0])
            except ValueError:
                continue
            num_headers = i
            break
        self.data_headers = [
            line.strip().split()
            for line in lines[data_header_start : data_header_start + num_headers]
        ]
        data_start = data_header_start + num_headers
        data_end = data_start + self.points
        str_data = lines[data_start:data_end]
        self.data = strArr2ndarray(str_data)

        return

    def add(self, other: "File") -> None:
        if not self.matchWith(other):
            raise Exception("Invalid file: data on not matching parameters")
        self.data[:, 2:] += other.data[:, 2:]
        return

    def write(self, path: str, overwrite: bool = False) -> bool:
        if not overwrite and os.path.exists(path):
            raise Exception("Output file already exists.")

        with open(path, "w") as f:
            f.write(f"  9809     {self.facility} {self.beamline}\n")
            f.write(
                f"  {self.filename}_editted {self.start_datetime} - {self.end_datetime}\n"
            )
            f.write(self.comment + "\n")
            f.write(self.ring + "\n")
            f.write(self.mono + "\n")
            f.write(
                f" {self.beamline} {self.MEASUERMENT_MODE[self.mode]}({self.mode}) Repetition=  {self.repetition} Points=  {self.points}\n"
            )
            f.write(
                f" Param file : {path}    energy axis({self.energy_axis})     Block =    {len(self.blocks)}\n"
            )

            f.write("\n")

            f.writelines(self.blocks.lines())

            f.write(" CT08(2)       NDCH =16\n")

            col_width: list[int] = [10, 8, 9, 9]
            num_datacols: int = self.data.shape[1] - 4
            for j in range(4, 4 + num_datacols):
                max = np.max(np.abs(self.data[:, j])) + 1
                col_width.append(int(np.floor(np.log10(max)) + 2))

            header = [
                [f"{ word:>{col_width[j]}}" for j, word in enumerate(line)]
                for line in self.data_headers
            ]

            for line in header:
                f.write(" ".join(line) + "\n")
            for i in range(self.data.shape[0]):
                row = self.data[i]
                line = [
                    f"{row[0]:>{col_width[0]}.4f}",
                    f"{row[1]:>{col_width[1]}.4f}",
                    f"{row[2]:>{col_width[2]}.2f}",
                ]
                introw = [int(val) for val in row]
                line += [f"{ introw[i]:>{col_width[i]}}" for i in range(3, len(row))]
                f.write(" ".join(line) + "\n")

        return True

    def matchWith(self, other: "File") -> bool:
        if self.facility != other.facility:
            print(
                f"Facility does not match. : self:{self.facility}, other:{other.facility}"
            )
            return False
        if self.beamline != other.beamline:
            print(
                f"Beamline does not match. : self:{self.beamline}, other:{other.beamline}"
            )
            return False
        if not self.blocks.matchWith(other.blocks):
            print("Blocks do not match.")
            print("self.blocks:")
            print("  " + "\n  ".join(self.blocks.lines()))
            print("other.blocks:")
            print("  " + "\n  ".join(other.blocks.lines()))
            return False
        return True


if __name__ == "__main__":
    import sys
    import os
    import argparse

    parser = argparse.ArgumentParser(description="Handle 9809 files.")
    parser.add_argument("command", metavar="COMMAND", help="command to execute")
    parser.add_argument("files", metavar="FILE", nargs="+", help="files to handle")
    parser.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        type=str,
        default="output.9809",
        help="output file name",
    )
    args = parser.parse_args()

    if args.command == "add":
        if os.path.exists(args.output):
            print(f"Output file `{args.output}` already exists.\nOverwrite? [y/N]")
            ans = input()
            if ans != "y":
                print("Canceled.")
                sys.exit(1)

        files = []
        for f in args.files:
            files.append(File(f))

        output = files[0]
        for f in files[1:]:
            output.add(f)

        if output.write(args.output, overwrite=True):
            print(f"Output file written to {args.output}")
        else:
            print("Failed to write output file.")
            sys.exit(1)
    else:
        print("Invalid command.")
        sys.exit(1)
