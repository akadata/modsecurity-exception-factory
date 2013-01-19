#-*- coding: utf-8 -*-
#
# Created on Jan 4, 2013
#
# @author: Younes JAAIDI
#
# $Id: $
#

from Orange.data.sql import SQLReader, __PostgresQuirkFix as PostgresQuirkFix
from contracts import contract, new_contract
from modsecurity_exception_factory.modsecurity_audit_data_source.i_modsecurity_audit_data_source import \
    IModsecurityAuditDataSource
from modsecurity_exception_factory.modsecurity_audit_data_source.modsecurity_audit_item_dict_iterable_sql import \
    ModsecurityAuditItemDictIterableSQL
from modsecurity_exception_factory.modsecurity_audit_data_source.sql_base import \
    SQLBase
from modsecurity_exception_factory.modsecurity_audit_data_source.sql_modsecurity_audit_entry_message import \
    SQLModsecurityAuditEntryMessage
from modsecurity_exception_factory.modsecurity_audit_data_source.sql_session_maker_for_with_statement import \
    SQLSessionMakerForWithStatement
from modsecurity_exception_factory.modsecurity_audit_entry import \
    ModsecurityAuditEntry
from sqlalchemy.engine import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.sql.expression import distinct
import sqlite3

new_contract('ModsecurityAuditEntry', ModsecurityAuditEntry)
new_contract('SQLModsecurityAuditEntryMessage', SQLModsecurityAuditEntryMessage)

class ModsecurityAuditDataSourceSQL(IModsecurityAuditDataSource):
    _DATA_INSERTION_BUFFER_SIZE = 100
    
    @contract
    def __init__(self, dataBaseUrl):
        """
    :type dataBaseUrl: unicode
"""
        self._dataBaseUrl = dataBaseUrl
        self._sqlEngine = create_engine(dataBaseUrl)
        self._sessionMaker = SQLSessionMakerForWithStatement(bind = self._sqlEngine)
        self._initialized = False

    def insertModsecurityAuditEntryIterable(self, modsecurityAuditEntryIterable):
        self._initializeDataBase()
        
        sqlModsecurityAuditEntryMessageBuffer = []
        
        for modsecurityAuditEntry in modsecurityAuditEntryIterable:
            hostName = modsecurityAuditEntry.hostName()
            requestFileName = modsecurityAuditEntry.requestFileName()
            for message in modsecurityAuditEntry.messageList():
                sqlMessage = SQLModsecurityAuditEntryMessage()
                sqlMessage.hostName = hostName
                sqlMessage.requestFileName = requestFileName
                sqlMessage.payloadContainer = message.payloadContainer()
                sqlMessage.ruleId = message.ruleId()
                
                # Insert message.
                self._insertModsecurityAuditEntryMessage(sqlModsecurityAuditEntryMessageBuffer, sqlMessage)
        
        self._flushModsecurityAuditEntryMessageBuffer(sqlModsecurityAuditEntryMessageBuffer)

    @contract
    def variableValueIterable(self, columnName):
        """
    :type columnName: str
"""
        if not self._columnExists(columnName):
            return
        
        with self._sessionMaker() as session:
            for row in session.query(distinct(getattr(SQLModsecurityAuditEntryMessage, columnName))):
                yield row[0]

    @contract
    def itemDictIterable(self, variableNameList):
        """
    :type variableNameList: list(str)
"""
        return ModsecurityAuditItemDictIterableSQL(self._sessionMaker, variableNameList)

    def orangeDataReader(self):        
        reader = SQLReader()
        
        # @hack SQLReader's connect method doesn't parse sqlite urls correctly.
        # It only handle file names instead of pathes (it should concatenate "host" and "path".        
        url = make_url(self._dataBaseUrl)
        if url.drivername == u"sqlite":
            reader.conn = sqlite3.connect(url.database)
            reader.quirks = PostgresQuirkFix(sqlite3)
        else:
            reader.connect(self._dataBaseUrl)
        
        return reader

    def _initializeDataBase(self):
        if self._initialized:
            return

        SQLBase.metadata.create_all(self._sqlEngine)
        self._initialized = True

    def _columnExists(self, columnName):
        return SQLModsecurityAuditEntryMessage.__table__.columns.has_key(columnName)

    @contract
    def _insertModsecurityAuditEntryMessage(self, sqlModsecurityAuditEntryMessageBuffer, sqlModsecurityAuditEntryMessage):
        """
    :type sqlModsecurityAuditEntryMessageBuffer: list(SQLModsecurityAuditEntryMessage)
    :type sqlModsecurityAuditEntryMessage: SQLModsecurityAuditEntryMessage
"""
        sqlModsecurityAuditEntryMessageBuffer.append(sqlModsecurityAuditEntryMessage)

        if len(sqlModsecurityAuditEntryMessageBuffer) >= self._DATA_INSERTION_BUFFER_SIZE:
            self._flushModsecurityAuditEntryMessageBuffer(sqlModsecurityAuditEntryMessageBuffer)

    @contract
    def _flushModsecurityAuditEntryMessageBuffer(self, sqlModsecurityAuditEntryMessageBuffer):
        """
    :type sqlModsecurityAuditEntryMessageBuffer: list(SQLModsecurityAuditEntryMessage)
"""
        with self._sessionMaker() as session:
            session.add_all(sqlModsecurityAuditEntryMessageBuffer)
            session.commit()
        del sqlModsecurityAuditEntryMessageBuffer[:]
