import pygame
import pygame.gfxdraw
import re
import math
import random


class Person:
    def __init__(self, name):
        self.name = name
        self.relations = {}
        self.pos = pygame.Vector2(0,0)

    def add_relation(self, name, score):
        self.relations[name] = score

    def update(self, people):
        p = self.relations
        for other in p:
            dist = self.pos.distance_to(people[other].pos)
            if dist > self.relations[other]:
                self.pos = self.pos.move_towards(people[other].pos, 0.001)
            elif dist < self.relations[other]:
                self.pos = self.pos.move_towards(people[other].pos, -0.001)
            #self.pos = self.pos.move_towards(people[other].pos, (self.pos.distance_to(people[other].pos) - self.relations[other]) * 0.01)


if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((1024, 1024))
    people_relations = {}
    people = {}
    distances = []

    with open("relations") as f:
        for line in f:
                name1, name2, score = line.split("|")

                for n in [name1, name2]:
                    if n not in people:
                        people[n] = Person(name1)

                fixed_score = float(score)
                people[name1].add_relation(name2, fixed_score)
                people[name2].add_relation(name1, fixed_score)
                
                distances.append(fixed_score)

    x_coord = 0
    y_coord = 0
    step = sum(distances) / len(distances)
    max_x = math.sqrt(len(people)) * step
    for p in people:
        people[p].pos.x = x_coord
        people[p].pos.y = y_coord
        print(f"Add at {x_coord},{y_coord}")
        x_coord += step
        if(x_coord > max_x):
            y_coord += step
            x_coord = 0
   
    ratio = screen.get_width() / max_x;


    line_limit = step
    running = True
    clock = pygame.time.Clock()
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    line_limit += 0.1
                if event.key == pygame.K_DOWN:
                    line_limit -= 0.1
        screen.fill((255,0,0))

        for p in people:
            screen.fill((0,255,0), (people[p].pos.x * ratio, people[p].pos.y * ratio,10,10))
            start_pos = (int(people[p].pos.x * ratio), int(people[p].pos.y * ratio))
            for o in people[p].relations:
                if (people[p].relations[o] < line_limit):
                    start_pos = (int(people[p].pos.x * ratio), int(people[p].pos.y * ratio))
                    end_pos = (int(people[o].pos.x * ratio), int(people[o].pos.y * ratio))
                    pygame.gfxdraw.line(screen, *start_pos ,*end_pos , (0,0,0))
            people[p].update(people)

        x_values = [p.pos.x for p in people.values()]
        offset_x = min(x_values)
        ratio_x = max(x_values) - offset_x
        for p in people:
            people[p].pos.x -= offset_x
        
        y_values = [p.pos.y for p in people.values()]
        offset_y = min(y_values)
        ratio_y = max(y_values) - offset_y
        for p in people:
            people[p].pos.y -= offset_y

        ratio = screen.get_width() / max(ratio_x, ratio_y)

        pygame.display.flip()
        clock.tick(60)
