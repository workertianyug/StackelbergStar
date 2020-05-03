import random

import sc2
from sc2 import Race, Difficulty
from sc2.constants import *
from sc2.player import Bot, Computer, Human

import numpy as np

# 0
gatewayPush = [[(NEXUS,2),(GATEWAY,3), (CYBERNETICSCORE,1)],
               [(ZEALOT,3, GATEWAY), (STALKER,3, GATEWAY)]]

# 1
roboPush = [[(NEXUS,2),(GATEWAY,2), (CYBERNETICSCORE,1), (ROBOTICSFACILITY,2)],
            [(ZEALOT,3,GATEWAY),(STALKER,3,GATEWAY),(IMMORTAL,3,ROBOTICSFACILITY)]]

betterRoboPush = [[(GATEWAY,2), (CYBERNETICSCORE,1), (ROBOTICSFACILITY,1)],
            [(STALKER,4,GATEWAY),(IMMORTAL,2,ROBOTICSFACILITY)]]

class StackelbergBot(sc2.BotAI):

    def __init__(self):
        # Initialize inherited class
        sc2.BotAI.__init__(self)

        self.MAX_WORKERS = 70
        self.scouts_and_spots = {}
        self.numPatrolWorkerIDs = []

        # strategy for StackelbergBot
        self.stackelbergStrats = [gatewayPush, betterRoboPush]

        self.stackelbergStratsName = ["gatewayPush", "roboPush"]

        # initial weights for expert voting
        self.EGVR = 1 # 0
        self.EGVI = 1 # 1
        self.LAII = 1 # 2
        self.MGVI = 1 # 3
        self.LGVI = 1 # 4
        self.MGVR = 1 # 5
        self.MGII = 1 # 6
        self.LGII = 1 # 7
        self.LGVR = 1 # 8
        self.LGVI = 1 # 9
        self.MGIR = 1 # 10
        self.LGIR = 1 # 11
        # put into numpy ary for computation
        self.weights_ary = np.array([self.EGVR, self.EGVI, self.LAII, self.MGVI, self.LGVI, self.MGVR,
                                     self.MGII, self.LGII, self.LGVR, self.LGVI, self.MGIR, self.LGIR])
        self.prob_ary = self.weights_ary / np.sum(self.weights_ary)

        # now need to define utility matrix (need to ensure has same number of columns as weights_ary)


        self.util_matrix = np.array(
            # 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11
            [[1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1], # 0 
             [10,1, 5, 5, 5, 7, 1, 7, 7, 3, 1, 1]] # 1  
        )



        # self.earlyStrat = [self.EGVR, self.EGVI]
        # self.midStrat = [self.MGVI, self.MGVR, self.MGII, self.MGIR]
        # self.lateStrat = [self.LAII, self.LGVI, self.LGII, self.LGVR, self.LGVI, self.LGIR]

        # self.groundStrat = [self.EGVR, self.EGVI, self.MGVI, self.MGVR, self.MGII,
        #                     self.LGII, self.LGVR, self.LGVI, self.LGIR]
        # self.airStrat = [self.LAII]

        # not sure if need the other two categories, maybe these two are enough

       
        self.naturalPos = self.get_next_expansion()


    async def on_step(self, iteration):

        await self.expert_voting(iteration)
        game_plan = self.getGamePlan(iteration) # get the game plan to execute
        await self.distribute_workers()
        await self.build_workers()
        await self.build_pylons()
        await self.build_assimilators()
        await self.worker_scout()
        await self.observer_scout()
        await self.execute_plan(game_plan)
        


    async def build_workers(self):
        
        if (len(self.structures(NEXUS)) * 22) > len(self.units(PROBE)) and len(self.units(PROBE)) < self.MAX_WORKERS:
            
            for nexus in self.structures(NEXUS).ready.idle:
                if self.can_afford(PROBE):
                    self.do(nexus.train(PROBE), subtract_cost=True, subtract_supply=True)

    async def build_pylons(self):
       
        if self.supply_left < 5 and not self.already_pending(PYLON):
            nexuses = self.structures(NEXUS).ready
            if nexuses.exists:
                if self.can_afford(PYLON):
                    await self.build(PYLON, near=self.structures.random)

    async def build_assimilators(self):
        
        for nexus in self.structures(NEXUS).ready:
            vaspenes = self.vespene_geyser.closer_than(15.0, nexus)
            for vaspene in vaspenes:
                if not self.can_afford(ASSIMILATOR):
                    break
                worker = self.select_build_worker(vaspene.position)
                if worker is None:
                    break
                if not self.structures(ASSIMILATOR).closer_than(1.0, vaspene).exists:
                    if self.units(PROBE).amount >= 15 and self.structures(GATEWAY).amount>0:
                        self.do(worker.build(ASSIMILATOR, vaspene), subtract_cost=True)

    async def worker_scout(self):

        # {DISTANCE_TO_ENEMY_START:EXPANSIONLOC}
        self.expand_dis_dir = {}

        for el in self.expansion_locations:
            distance_to_enemy_start = el.distance_to(self.enemy_start_locations[0])
            #print(distance_to_enemy_start)
            self.expand_dis_dir[distance_to_enemy_start] = el

        self.ordered_exp_distances = sorted(k for k in self.expand_dis_dir)


        # remove nonexistent patrol workers
        if len(self.numPatrolWorkerIDs) != 0:
            for workerid in self.numPatrolWorkerIDs:
                if workerid not in [unit.tag for unit in self.units]:
                    self.numPatrolWorkerIDs.remove(workerid)

        if len(self.numPatrolWorkerIDs) == 0:
            # select a random worker
            patrolWorker = self.workers.random
            self.do(patrolWorker.move(self.enemy_start_locations[0]))
            self.do(patrolWorker.patrol(self.expand_dis_dir[self.ordered_exp_distances[1]], queue=True))
            self.do(patrolWorker.patrol(self.expand_dis_dir[self.ordered_exp_distances[2]], queue=True))
            self.numPatrolWorkerIDs.append(patrolWorker.tag)

    async def observer_scout(self):
        # only if there's a ROBO we do observer scout
        if self.structures(ROBOTICSFACILITY):
            for robo in self.structures(ROBOTICSFACILITY):
                if (self.can_afford(OBSERVER)) and (self.units(OBSERVER).amount + self.already_pending(OBSERVER) < 3):
                    self.do(robo.train(OBSERVER), subtract_cost=True, subtract_supply=True)

        for obsr in self.units(OBSERVER):
            if obsr.is_idle:
                self.do(obsr.move(self.enemy_start_locations[0]))
                self.do(obsr.patrol(self.expand_dis_dir[self.ordered_exp_distances[1]], queue=True))
                self.do(obsr.patrol(self.expand_dis_dir[self.ordered_exp_distances[2]], queue=True))



    async def execute_plan(self, game_plan):

        [structure_plan, unit_plan] = game_plan

        for (cur_structure, num) in structure_plan:
            # question for later: how to prioritize cybercore(soln found: keep record of supply workers)
            if (cur_structure == NEXUS and
                self.can_afford(NEXUS) and 
                self.structures(NEXUS).amount < num):
                await self.expand_now()
            elif self.can_afford(cur_structure) and self.structures(cur_structure).amount < num:
                await self.build(cur_structure, near=self.structures(PYLON).random)


        for (cur_unit, num, production) in unit_plan:
 
            cur_productions = self.structures(production).ready.idle
            for p in cur_productions:
                if (self.can_afford(cur_unit) and
                    (self.units(cur_unit).amount + self.already_pending(cur_unit)) < num):
                    self.do(p.train(cur_unit), subtract_cost=True, subtract_supply=True)
                    

        # if army prep is complete -> attack
        canAttack = True
        for (cur_unit, num, production) in unit_plan:
            if self.units(cur_unit).amount < num:
                canAttack = False
        if canAttack == True:
            for (cur_unit, num, production) in unit_plan:
                for u in self.units(cur_unit):
                    self.do(u.attack(self.enemy_start_locations[0]))
        # todo: how to move around units
        # else:
        #     # gather at natural expansion
        #     for a in self.units:
        #         if a.type_id != PROBE and a.is_idle:
        #             self.do(a.move(self.expand_dis_dir[self.ordered_exp_distances[-2]]))


    async def expert_voting(self, iteration):
        # roughly every 30 seconds in game
        if iteration % 80 != 0:
            return

        print(iteration)
        eps = 0.1
        print(self.enemy_structures)
        if self.enemy_structures(GATEWAY).amount > 2 and self.units(PROBE).amount < 22:
            self.EGVI *= (1+eps)

        if self.enemy_structures(FORGE).amount > 0 and self.units(PROBE).amount < 22:
            self.EGVI *= (1+eps)

        if self.enemy_structures(ROBOTICSFACILITY).amount > 0:
            self.MGVI *= (1+eps)
            self.LGVI *= (1+eps)

        if self.enemy_structures(STARGATE):
            self.LAII *= (1+eps)
            # self.MAVI *= (1+eps)

        if self.enemy_structures(TWILIGHTCOUNCIL):
            self.MGVR *= (1+eps)
            self.MGIR *= (1+eps)
            self.LGVR *= (1+eps)

        if self.enemy_structures(ROBOTICSBAY):
            self.LGVI *= (1+eps)

        if self.enemy_structures(TEMPLARARCHIVE):
            self.LGVR *= (1+eps)

        if self.enemy_structures(FLEETBEACON):
            self.LAII *= (1+eps)

        if self.enemy_structures(DARKSHRINE):
            self.MGIR *= (1+eps)
            self.LGIR *= (1+eps)


    def getGamePlan(self, iteration):

        # solve the game matrix return a game plan
        # for opponent's probability use weights

        # just get the max out of all the probabilities?

        self.weights_ary = np.array([self.EGVR, self.EGVI, self.LAII, self.MGVI, self.LGVI, self.MGVR,
                                     self.MGII, self.LGII, self.LGVR, self.LGVI, self.MGIR, self.LGIR])
        self.prob_ary = self.weights_ary / np.sum(self.weights_ary)

        best_i = 0
        best_util = -1

        for i in range(len(self.stackelbergStrats)):
            cur_row = self.util_matrix[i]
            cur_util = np.dot(cur_row, self.prob_ary)

            if cur_util > best_util:
                best_util = cur_util
                best_i = i

        if iteration % 80 == 0:
            print("curstrat: ", self.stackelbergStratsName[best_i])

        return self.stackelbergStrats[best_i]











# def main():
#     sc2.run_game(
#         sc2.maps.get("(2)CatalystLE"),
#         [Human(Race.Protoss),Bot(Race.Protoss, StackelbergBot(), name="StackelbergBot")],
#         realtime=True,
#     )

def main():
    sc2.run_game(
        sc2.maps.get("(2)CatalystLE"),
        [Bot(Race.Protoss, StackelbergBot(), name="StackelbergBot"), Computer(Race.Protoss, Difficulty.Medium)],
        realtime=False,
    )

if __name__ == "__main__":
    main()



     
# get function executeRoadMap (done)

# take in dictionary of structures and units (done)

# if fullfilled, attack (done)

# dont' forget to expand -> could be included in the roadmap (done)

# observer scout (done)


# stackelberg solver

# expert voting algo

# use enemy scouting info

# how to make units defend? can have all army units gather at natural (need to keep track of all army)












































