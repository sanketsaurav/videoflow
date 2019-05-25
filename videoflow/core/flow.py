from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging

from .constants import BATCH, REALTIME, FLOW_TYPES, STOP_SIGNAL
from .node import Node, ProducerNode, ConsumerNode, ProcessorNode
from .task import Task, ProducerTask, ProcessorTask, ConsumerTask
from ..environments.queues import QueueExecutionEnvironment

logger = logging.getLogger(__package__)

def _has_cycle_util(v : Node, visited, rec):
    visited[v] = True
    rec[v] = True
    
    for child in v.children:
        if not child in visited:
            visited[child] = False
        if visited[child] == False:
            if _has_cycle_util(child, visited, rec):
                return True
        elif rec[child] == True:
            return True
    
    rec[v] = False
    return False

def has_cycle(producers):
    '''
    Used to detect if the graph is not acyclical.  Returns true if it \
    finds a cycle in the graph.  It begins exploring the graph from producers down \
    all the way to consumers.
    '''
    visited = {}
    rec = {}
    for v in producers:
        visited[v] = False
        rec[v] = False
    
    for v in producers:
        if visited[v] == False:
            if _has_cycle_util(v, visited, rec):
                return True
    return False
    
def _topological_sort_util(v : Node, visited, stack):
    if not v in visited:
        visited[v] = False
    visited[v] = True
    for child in v.children:
        if not child in visited or visited[child] == False:
            _topological_sort_util(child, visited, stack)
    stack.insert(0, v)

def topological_sort(producers):
    '''
    Creates a topological sort of the computation graph.

    - Arguments:
        - producers: a list of producer nodes, that is, nodes with no parents.
    
    - Returns:
        - stack: a list of nodes in topological order.  If \
            a *node A* appears before a *node B* on the list, it means \
            that *node A* does not depend on *node B* output
    '''
    visited = {}
    for v in producers:
        visited[v] = False
    stack = []

    for v in producers:
        if visited[v] == False:
            _topological_sort_util(v, visited, stack)
    
    return stack

class Flow:
    '''
    Represents a linear flow of data from one task to another.\
    Note that a flow is created from a **directed acyclic graph** of producer, processor \
    and consumer nodes, but the flow itself is **linear**, because it is an optimized \
    `topological sort` of the directed acyclic graph.

    - Arguments:
        - producers: a list of producer nodes of type ``videoflow.core.node.ProducerNode``.
        - consumers: a list of consumer nodes of type ``videoflow.core.node.ConsumerNode``.
        - flow_type: one of 'realtime' or 'batch'
    '''
    def __init__(self, producers, consumers, flow_type = REALTIME):
        if len(producers) != 1:
            raise AttributeError('Only support flows with 1 producer for now.')
        for producer in producers:
            if not isinstance(producer, ProducerNode):
                raise AttributeError('{} is not instance of ProducerNode'.format(producer))
         
        self._producers = producers
        self._consumers = consumers
        if flow_type not in FLOW_TYPES:
            raise ValueError('flow_type must be one of {}'.format(','.join(FLOW_TYPES)))
        
        if has_cycle(self._producers):
            logger.error('Cycle detected in computation graph. Exiting now...')
            raise ValueError('Cycle found in graph')
        # **** IMPORTANT****** This should be done in the
        # constructor
        #2. TODO: CHeck that all nodes in the graph are
        # descendants of a producer
        #3. TODO: Check that all producers' results are
        #being read by a consumer.

        self._execution_environment = QueueExecutionEnvironment(flow_type)

    def run(self):
        '''
        Simple documentation: It starts the flow. 

        More complex documentation: 
        
        1. It creates a topological sort of the nodes in the \
            computation graph, and wraps each node around a ``videoflow.core.task.Task``
        2. It passes the tasks to the environment, which allocates them and creates the \
            channels that will be used for communication between tasks. Tasks themselves \
            do not know where this channels are, but the environment assigns a messenger \
            to each task that knows how to communicate in those channels.
        '''

        #1. Build a topological sort of the graph.
        tsort = topological_sort(self._producers)
        #2. TODO: OPtimize graph in the following ways:   
        # a) Tasks do not need to pass down to children
        # all of the outputs of parents.  Hence, at a given
        # level of the topological sort, have the list of 
        # inputs from parents that are not needed below that 
        # level

        # b) Not all the processors have to write to a pub/sub channel
        # If their output is only needed by the next preprocessor and non one
        # else below in the graph, then I can string subsequent preprocessors together
        # a big preprocessor
        
        #3. Create the tasks and the input/outputs
        # for them
        # task_data is a list of tuples (node, task_id, parent_task_id, has_chilren)
        tasks_data = []

        for i, node in enumerate(tsort):
            if isinstance(node, ProducerNode):
                task_data = (node, i, None, i < (len(tsort) - 1))
            elif isinstance(node, ProcessorNode):
                task_data = (node, i, i - 1, i < (len(tsort) - 1))
            elif isinstance(node, ConsumerNode):
                task_data = (node, i, i - 1, i < (len(tsort) - 1))
            else:
                raise ValueError('node is not of one of the valid types')
            tasks_data.append(task_data)
        
        # 4. Put each task to run in the place where the processor it
        # contains inside runs.
        self._execution_environment.allocate_and_run_tasks(tasks_data)
        logger.info('Allocated processes for {} tasks'.format(len(tasks_data)))
        logger.info('Started running flow.')
    
    def join(self):
        '''
        Blocking method. Will make the process that calls this method block until the flow finishes
        running naturally.
        '''
        self._execution_environment.join_task_processes()
        logger.info('Flow has stopped.')

    def stop(self):
        '''
        Blocking method. Stops the flow.  Makes the execution environment send a flow termination signal.
        '''
        logger.info('Stop termination signal placed on flow.')
        self._execution_environment.signal_flow_termination()
        self.join()
