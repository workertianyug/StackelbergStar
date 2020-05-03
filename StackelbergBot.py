import random

import sc2
from sc2 import Race, Difficulty
from sc2.constants import *
from sc2.player import Bot, Computer, Human


gatewayPush = [[(NEXUS,2),(GATEWAY,3), (CYBERNETICSCORE,1)],
               [(ZEALOT,3, GATEWAY), (STALKER,3, GATEWAY)]]

roboPush = [[(NEXUS,2),(GATEWAY,2), (CYBERNETICSCORE,1), (ROBOTICSFACILITY,2)],
            [(ZEALOT,3,GATEWAY),(STALKER,3,GATEWAY),(IMMORTAL,3,ROBOTICSFACILITY)]]

class StackelbergBot(sc2.BotAI):

    def __init__(self):
        # Initialize inherited class
        sc2.BotAI.__init__(self)

        self.MAX_WORKERS = 70
        self.scouts_and_spots = {}
        self.numPatrolWorkerIDs = []

        # weights for expert voting

        self.EGVR = 1
        self.EGVI = 1
        self.LAII = 1
        self.MGVI = 1
        self.LGVI = 1
        self.MGVR = 1
        self.MGII = 1
        self.LGII = 1
        self.LGVR = 1
        self.LGVI = 1
        self.MGIR = 1
        self.LGIR = 1

        self.earlyStrat = [self.EGVR, self.EGVI]
        self.midStrat = [self.MGVI, self.MGVR, self.MGII, self.MGIR]
        self.lateStrat = [self.LAII, self.LGVI, self.LGII, self.LGVR, self.LGVI, self.LGIR]

        self.groundStrat = [self.EGVR, self.EGVI, self.MGVI, self.MGVR, self.MGII,
                            self.LGII, self.LGVR, self.LGVI, self.LGIR]
        self.airStrat = [self.LAII]

        # not sure if need the other two categories, maybe these two are enough



    async def on_step(self, iteration):

        await self.distribute_workers()
        await self.build_workers()
        await self.build_pylons()
        await self.build_assimilators()
        await self.worker_scout()
        await self.observer_scout()
        await self.execute_plan(roboPush)
        await self.expert_voting(iteration)


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


    async def getGamePlan(self):

        # solve the game matrix return a game plan
        # for opponent's probability use weights

        # just get the max out of all the probabilities?
        pass











def main():
    sc2.run_game(
        sc2.maps.get("(2)CatalystLE"),
        [Human(Race.Protoss),Bot(Race.Protoss, StackelbergBot(), name="StackelbergBot")],
        realtime=True,
    )

# def main():
#     sc2.run_game(
#         sc2.maps.get("(2)CatalystLE"),
#         [Bot(Race.Protoss, StackelbergBot(), name="StackelbergBot"), Computer(Race.Protoss, Difficulty.Easy)],
#         realtime=True,
#     )

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












































