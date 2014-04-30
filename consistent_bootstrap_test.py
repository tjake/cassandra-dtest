import time

from dtest import Tester, debug
from assertions import assert_unavailable
from tools import (create_c1c2_table, insert_c1c2, query_c1c2, retry_till_success,
                   insert_columns, new_node, no_vnodes)

class TestBootstrapConsistency(Tester):

    @no_vnodes()
    def consistent_reads_after_move_test(self):
        debug("Creating a ring")
        cluster = self.cluster
        cluster.set_configuration_options(values={ 'hinted_handoff_enabled' : False, 'write_request_timeout_in_ms' : 60000, 'read_request_timeout_in_ms' : 60000, 'dynamic_snitch_badness_threshold' : 0.0}, batch_commitlog=True)
    
        cluster.populate(3, tokens=[0, 2**48, 2**62]).start()
        [node1, node2, node3] = cluster.nodelist()
        cluster.start()

        debug("Set to talk to node 2")
        n2cursor = self.patient_cql_connection(node2).cursor()
        self.create_ks(n2cursor, 'ks', 2)
        create_c1c2_table(self, n2cursor)

        debug("Generating some data for all nodes")
        for n in xrange(10,20):
            insert_c1c2(n2cursor, n, 'ALL')

        node1.flush()
        debug("Taking down node1")
        node1.stop(wait_other_notice=True)

        debug("Writing data to node2")
        for n in xrange(30,1000):
            insert_c1c2(n2cursor, n, 'ONE')
        node2.flush()

        debug("Restart node1")
        node1.start(wait_other_notice=True)

        debug("Move token on node3")
        node3.move(2)

        debug("Checking that no data was lost")
        for n in xrange(10,20):
            query_c1c2(n2cursor, n, 'ALL')

        for n in xrange(30,1000):
            query_c1c2(n2cursor, n, 'ALL')

    def consistent_reads_after_bootstrap_test(self):
        debug("Creating a ring")
        cluster = self.cluster
        cluster.set_configuration_options(values={ 'hinted_handoff_enabled' : False, 'write_request_timeout_in_ms' : 60000, 'read_request_timeout_in_ms' : 60000, 'dynamic_snitch_badness_threshold' : 0.0}, batch_commitlog=True)
    
        cluster.populate(2).start()
        [node1, node2] = cluster.nodelist()
        cluster.start()

        debug("Set to talk to node 2")
        n2cursor = self.patient_cql_connection(node2).cursor()
        self.create_ks(n2cursor, 'ks', 2)
        create_c1c2_table(self, n2cursor)

        debug("Generating some data for all nodes")
        for n in xrange(10,20):
            insert_c1c2(n2cursor, n, 'ALL')

        node1.flush()
        debug("Taking down node1")
        node1.stop(wait_other_notice=True)

        debug("Writing data to only node2")
        for n in xrange(30,1000):
            insert_c1c2(n2cursor, n, 'ONE')
        node2.flush()

        debug("Restart node1")
        node1.start(wait_other_notice=True)

        debug("Boostraping node3")
        node3 = new_node(cluster)
        node3.start()

        n3cursor = self.patient_cql_connection(node3).cursor()
        n3cursor.execute("USE ks");
        debug("Checking that no data was lost")
        for n in xrange(10,20):
            query_c1c2(n3cursor, n, 'ALL')

        for n in xrange(30,1000):
            query_c1c2(n3cursor, n, 'ALL')

    def consistent_reads_after_relocate_test(self):
        debug("Creating a ring")
        cluster = self.cluster
        cluster.set_configuration_options(values={
                'initial_token': None, 
                'num_tokens': 10,
                'hinted_handoff_enabled' : False, 
                'write_request_timeout_in_ms' : 60000, 
                'read_request_timeout_in_ms' : 60000, 
                'dynamic_snitch_badness_threshold' : 0.0}, batch_commitlog=True)
    
        cluster.populate(3).start()
        [node1, node2, node3] = cluster.nodelist()
        cluster.start()
       
        debug("Set to talk to node 2")
        n2cursor = self.patient_cql_connection(node2).cursor()
        self.create_ks(n2cursor, 'ks', 2)
        create_c1c2_table(self, n2cursor)

        debug("Generating some data for all nodes")
        for n in xrange(10,20):
            insert_c1c2(n2cursor, n, 'ALL')

        node1.flush()
        debug("Taking down node1")
        node3.stop(wait_other_notice=True)
        
        debug("Writing data to node2")
        for n in xrange(30,1000):
            insert_c1c2(n2cursor, n, 'ONE')
        node2.flush()

        debug("Restart node1")
        node3.start(wait_other_notice=True)
        
        debug("Getting token from node 1")
        n1cursor = self.patient_cql_connection(node1).cursor()
        n1cursor.execute('SELECT tokens FROM system.local')
        tokens = n1cursor.fetchone()

        debug("Relocate tokens from node1 to node3")
        i = 0;
        tl = "";
        for t in tokens[0]:
            if i == 8:
                break
            tl = "%s %s" % (tl, t);
            i += 1

        cmd = "taketoken %s" % tl
        debug(cmd)
        node3.nodetool(cmd)

        n1cursor.execute('SELECT tokens FROM system.local')
        tokens = n1cursor.fetchone()
        debug("%s" % tokens)
        assert len(tokens) == 2


        debug("Checking that no data was lost")
        for n in xrange(10,20):
            query_c1c2(n2cursor, n, 'ALL')

        for n in xrange(30,1000):
            query_c1c2(n2cursor, n, 'ALL')

