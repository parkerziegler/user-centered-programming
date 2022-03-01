from z3 import *
import sys

# This algorithm works by deriving:
# 1) The maximum movements that the robot can make in any direction
#    based on its current position in an arbitrary grid of size (r, c).
# 2) The maximum movements that the robot can make in any direction
#    based on its current position and the positions of n obstacles.
#
# We encode the grid using 0-indexed integers placed from left to right.
# For example, a 3x3 grid in our encoding would be represented as:
#
# 0  1  2
# 3  4  5
# 6  7  8
#
# We arbitrarily bound the search to a maximum instruction set depth of
# 10, but this can be altered by setting max_depth.
#
# BEGIN IMPLEMENTATION
# -----------------------------------------------------------------------------
#
# A helper function to check if there is an obstacle in the same row
# as the robot's current position.
def obstacle_in_same_row(row_index, obstacle, envir):
    return row_index == (obstacle - obstacle % envir[1]) / envir[1]


# A helper function to check if there is an obstacle in the same column
# as the robot's current position.
def obstacle_in_same_column(col_index, obstacle, envir):
    return col_index == obstacle % envir[1]


# The core instruction algorithm.
def run_instr(pos, instr, arg, envir, obstacles):
    # Determine maximum movements in all directions based on the robot's
    # current position and the size of the environment.
    max_left = pos % envir[1]
    max_right = envir[1] - max_left - 1
    max_up = (pos - max_left) / envir[1]
    max_down = envir[0] - max_up - 1

    # Add constraints to evade obstacles. If an obstacle is not in the
    # same row or column as the robot's current position, ignore it.
    # Otherwise, ensure the robot can only move up to that position.
    evade_left_obstacles = [
        Or(
            Not(obstacle_in_same_row(max_up, obstacle, envir)),
            pos - arg > obstacle,  # Move L up to the obstacle.
            pos < obstacle,  # Obstacle is on the right.
        )
        for obstacle in obstacles
    ]
    evade_right_obstacles = [
        Or(
            Not(obstacle_in_same_row(max_up, obstacle, envir)),
            pos + arg < obstacle,  # Move R up to the obstacle.
            obstacle < pos,  # Obstacle is on the left.
        )
        for obstacle in obstacles
    ]
    evade_obstacles_above = [
        Or(
            Not(obstacle_in_same_column(max_left, obstacle, envir)),
            pos - arg * envir[1] > obstacle,  # Move U up to the obstacle.
            pos < obstacle,  # Obstacle is beneath.
        )
        for obstacle in obstacles
    ]
    evade_obstacles_below = [
        Or(
            Not(obstacle_in_same_column(max_left, obstacle, envir)),
            pos + arg * envir[1] < obstacle,  # Move D down to the obstacle.
            obstacle < pos,  # Obstacle is above.
        )
        for obstacle in obstacles
    ]

    mvmt_constraints = If(
        arg > 0,
        If(
            instr == 0,
            If(
                And(*evade_left_obstacles, arg <= max_left),
                pos - arg,
                pos,
            ),
            If(
                instr == 1,
                If(
                    And(*evade_right_obstacles, arg <= max_right),
                    pos + arg,
                    pos,
                ),
                If(
                    instr == 2,
                    If(
                        And(*evade_obstacles_above, arg <= max_up),
                        pos - arg * envir[1],
                        pos,
                    ),
                    If(
                        And(*evade_obstacles_below, arg <= max_down),
                        pos + arg * envir[1],
                        pos,
                    ),
                ),
            ),
        ),
        pos,
    )

    return mvmt_constraints


def run_prog(pos, instrs, args, envir, obstacles):
    curr_pos = pos
    for i in range(len(instrs)):
        curr_pos = run_instr(curr_pos, instrs[i], args[i], envir, obstacles)
    return curr_pos


def gen_instrs(num_instrs):
    return [BitVec("x_" + str(i), 2) for i in range(num_instrs)]


def gen_args(num_instrs):
    return [Int("a_" + str(i)) for i in range(num_instrs)]


def sow_obstacles(obstacles, envir):
    obs = []
    print("Sowing chaos.")

    for obstacle in obstacles:
        if obstacle > envir[0] * envir[1] - 1:
            print(f"Cell {obstacle} is outside of environment bounds. Discarding.")
        else:
            print(f"Placing obstacle in cell {obstacle}.")
            obs.append(obstacle)

    return obs


def print_model(model, instrs, args):
    for i in range(len(instrs)):
        val = model.eval(instrs[i])
        arg = model.eval(args[i])
        if val == 0:
            print("L", arg)
        elif val == 1:
            print("R", arg)
        elif val == 2:
            print("U", arg)
        elif val == 3:
            print("D", arg)
        else:
            print("-")


# Implement iterative deepening to attempt to find a solution in the shortest
# number of instructions. Start from 1 instruction and increase to a max_depth of 10.
num_instrs = 1
solution_found = False
max_depth = 10

# Define a starting position, target position, environment size, and obstacles.
# For this case, we use a 4x4 grid with obstacles at cells 2, 5, 11, and 12.
start_pos = 0
target_pos = 15
envir = (4, 4)
obstacles = [2, 5, 11, 12]
obs = sow_obstacles(obstacles, envir)

while not solution_found:
    instrs = gen_instrs(num_instrs)
    args = gen_args(num_instrs)

    goal = run_prog(start_pos, instrs, args, envir, obs) == target_pos

    s = Solver()
    s.add(goal)
    satisfiable = s.check()
    print("satisfiable?", satisfiable)

    if satisfiable == sat:
        solution_found = True
        model = s.model()
        print_model(model, instrs, args)
        print(model)
    else:
        if num_instrs > max_depth:
            print("Max depth exceeded and no solution has been found. Exiting.")
            sys.exit()

        print(
            f"Could not find a solution with num_instrs {num_instrs}. Incrementing to {num_instrs + 1}."
        )
        num_instrs += 1
