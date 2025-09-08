import asyncpg
import logging
from typing import Dict, Any, List, Optional
from config import settings

logger = logging.getLogger(__name__)


class PostgreSQLConfigAnalyzer:
    """Анализатор конфигурации PostgreSQL для получения рекомендаций по настройкам"""
    
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or settings.database_url
    
    async def get_configuration_analysis(self) -> Dict[str, Any]:
        """
        Получает и анализирует конфигурацию PostgreSQL
        """
        try:
            conn = await asyncpg.connect(self.database_url)
            try:
                # Получаем основные настройки
                settings_data = await self._get_settings(conn)
                
                # Получаем информацию о системе
                system_info = await self._get_system_info(conn)
                
                # Получаем статистику
                stats = await self._get_statistics(conn)
                
                # Анализируем и генерируем рекомендации
                analysis = self._analyze_configuration(settings_data, system_info, stats)
                
                return {
                    'settings': settings_data,
                    'system_info': system_info,
                    'statistics': stats,
                    'analysis': analysis,
                    'recommendations': self._generate_config_recommendations(settings_data, system_info, stats)
                }
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"Error analyzing PostgreSQL configuration: {e}")
            raise
    
    async def _get_settings(self, conn: asyncpg.Connection) -> Dict[str, Any]:
        """Получает основные настройки PostgreSQL"""
        settings_query = """
        SELECT name, setting, unit, context, short_desc
        FROM pg_settings 
        WHERE name IN (
            'shared_buffers', 'work_mem', 'maintenance_work_mem', 'effective_cache_size',
            'random_page_cost', 'seq_page_cost', 'cpu_tuple_cost', 'cpu_index_tuple_cost',
            'cpu_operator_cost', 'max_connections', 'checkpoint_completion_target',
            'wal_buffers', 'checkpoint_segments', 'checkpoint_timeout',
            'log_min_duration_statement', 'log_statement', 'log_line_prefix',
            'deadlock_timeout', 'lock_timeout', 'statement_timeout',
            'autovacuum', 'autovacuum_max_workers', 'autovacuum_naptime'
        )
        ORDER BY name
        """
        
        rows = await conn.fetch(settings_query)
        settings_dict = {}
        
        for row in rows:
            settings_dict[row['name']] = {
                'value': row['setting'],
                'unit': row['unit'],
                'context': row['context'],
                'description': row['short_desc']
            }
        
        return settings_dict
    
    async def _get_system_info(self, conn: asyncpg.Connection) -> Dict[str, Any]:
        """Получает информацию о системе"""
        system_queries = {
            'version': "SELECT version() as version",
            'database_size': "SELECT pg_size_pretty(pg_database_size(current_database())) as size",
            'total_connections': "SELECT count(*) as total FROM pg_stat_activity",
            'active_connections': "SELECT count(*) as active FROM pg_stat_activity WHERE state = 'active'",
            'idle_connections': "SELECT count(*) as idle FROM pg_stat_activity WHERE state = 'idle'",
            'max_connections': "SELECT setting::int as max_conn FROM pg_settings WHERE name = 'max_connections'",
            'shared_buffers': "SELECT setting as shared_buffers FROM pg_settings WHERE name = 'shared_buffers'",
            'work_mem': "SELECT setting as work_mem FROM pg_settings WHERE name = 'work_mem'"
        }
        
        system_info = {}
        for key, query in system_queries.items():
            try:
                result = await conn.fetchrow(query)
                if result:
                    system_info[key] = result[0] if len(result) == 1 else dict(result)
            except Exception as e:
                logger.warning(f"Failed to get {key}: {e}")
                system_info[key] = None
        
        return system_info
    
    async def _get_statistics(self, conn: asyncpg.Connection) -> Dict[str, Any]:
        """Получает статистику базы данных"""
        stats_queries = {
            'database_stats': """
                SELECT 
                    numbackends as active_connections,
                    xact_commit as committed_transactions,
                    xact_rollback as rolled_back_transactions,
                    blks_read as blocks_read,
                    blks_hit as blocks_hit,
                    tup_returned as tuples_returned,
                    tup_fetched as tuples_fetched,
                    tup_inserted as tuples_inserted,
                    tup_updated as tuples_updated,
                    tup_deleted as tuples_deleted
                FROM pg_stat_database 
                WHERE datname = current_database()
            """,
            'table_stats': """
                SELECT 
                    schemaname,
                    tablename,
                    n_tup_ins as inserts,
                    n_tup_upd as updates,
                    n_tup_del as deletes,
                    n_live_tup as live_tuples,
                    n_dead_tup as dead_tuples,
                    last_vacuum,
                    last_autovacuum,
                    last_analyze,
                    last_autoanalyze
                FROM pg_stat_user_tables
                ORDER BY n_live_tup DESC
                LIMIT 20
            """,
            'index_stats': """
                SELECT 
                    schemaname,
                    tablename,
                    indexname,
                    idx_tup_read as index_tuples_read,
                    idx_tup_fetch as index_tuples_fetched,
                    idx_scan as index_scans
                FROM pg_stat_user_indexes
                WHERE idx_scan > 0
                ORDER BY idx_scan DESC
                LIMIT 20
            """,
            'connection_stats': """
                SELECT 
                    state,
                    count(*) as count
                FROM pg_stat_activity
                GROUP BY state
            """
        }
        
        stats = {}
        for key, query in stats_queries.items():
            try:
                if key == 'database_stats':
                    result = await conn.fetchrow(query)
                    stats[key] = dict(result) if result else {}
                else:
                    results = await conn.fetch(query)
                    stats[key] = [dict(row) for row in results]
            except Exception as e:
                logger.warning(f"Failed to get {key} stats: {e}")
                stats[key] = []
        
        return stats
    
    def _analyze_configuration(self, settings: Dict[str, Any], system_info: Dict[str, Any], stats: Dict[str, Any]) -> Dict[str, Any]:
        """Анализирует конфигурацию и выявляет проблемы"""
        analysis = {
            'memory_usage': self._analyze_memory_settings(settings, system_info),
            'connection_usage': self._analyze_connection_usage(system_info),
            'performance_indicators': self._analyze_performance_indicators(stats),
            'maintenance_issues': self._analyze_maintenance_issues(stats),
            'overall_health': 'good'
        }
        
        # Определяем общее состояние
        issues = []
        if analysis['memory_usage']['issues']:
            issues.extend(analysis['memory_usage']['issues'])
        if analysis['connection_usage']['issues']:
            issues.extend(analysis['connection_usage']['issues'])
        if analysis['performance_indicators']['issues']:
            issues.extend(analysis['performance_indicators']['issues'])
        
        if len(issues) > 5:
            analysis['overall_health'] = 'poor'
        elif len(issues) > 2:
            analysis['overall_health'] = 'fair'
        
        analysis['total_issues'] = len(issues)
        analysis['issues'] = issues
        
        return analysis
    
    def _analyze_memory_settings(self, settings: Dict[str, Any], system_info: Dict[str, Any]) -> Dict[str, Any]:
        """Анализирует настройки памяти"""
        issues = []
        recommendations = []
        
        # Анализ shared_buffers
        shared_buffers = settings.get('shared_buffers', {}).get('value', '0')
        if shared_buffers and shared_buffers != '0':
            try:
                shared_buffers_mb = int(shared_buffers.replace('MB', '').replace('GB', ''))
                if shared_buffers_mb < 128:
                    issues.append("shared_buffers слишком мал (< 128MB)")
                    recommendations.append("Увеличьте shared_buffers до 25% от RAM")
            except ValueError:
                pass
        
        # Анализ work_mem
        work_mem = settings.get('work_mem', {}).get('value', '0')
        if work_mem and work_mem != '0':
            try:
                work_mem_mb = int(work_mem.replace('MB', '').replace('kB', ''))
                if work_mem_mb < 4:
                    issues.append("work_mem слишком мал (< 4MB)")
                    recommendations.append("Увеличьте work_mem до 4-16MB")
                elif work_mem_mb > 64:
                    issues.append("work_mem слишком велик (> 64MB)")
                    recommendations.append("Уменьшите work_mem до 16-32MB")
            except ValueError:
                pass
        
        return {
            'issues': issues,
            'recommendations': recommendations,
            'status': 'good' if not issues else 'needs_attention'
        }
    
    def _analyze_connection_usage(self, system_info: Dict[str, Any]) -> Dict[str, Any]:
        """Анализирует использование подключений"""
        issues = []
        recommendations = []
        
        active_connections = system_info.get('active_connections', 0)
        max_connections = system_info.get('max_connections', 0)
        
        if max_connections > 0:
            usage_percentage = (active_connections / max_connections) * 100
            
            if usage_percentage > 80:
                issues.append(f"Высокое использование подключений: {usage_percentage:.1f}%")
                recommendations.append("Рассмотрите увеличение max_connections или оптимизацию пула подключений")
            elif usage_percentage > 60:
                issues.append(f"Среднее использование подключений: {usage_percentage:.1f}%")
                recommendations.append("Мониторьте использование подключений")
        
        return {
            'issues': issues,
            'recommendations': recommendations,
            'usage_percentage': usage_percentage if max_connections > 0 else 0,
            'status': 'good' if not issues else 'needs_attention'
        }
    
    def _analyze_performance_indicators(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Анализирует показатели производительности"""
        issues = []
        recommendations = []
        
        db_stats = stats.get('database_stats', {})
        
        # Анализ hit ratio
        blocks_hit = db_stats.get('blocks_hit', 0)
        blocks_read = db_stats.get('blocks_read', 0)
        
        if blocks_hit + blocks_read > 0:
            hit_ratio = blocks_hit / (blocks_hit + blocks_read) * 100
            if hit_ratio < 90:
                issues.append(f"Низкий hit ratio: {hit_ratio:.1f}%")
                recommendations.append("Увеличьте shared_buffers для улучшения hit ratio")
        
        # Анализ соотношения коммитов к роллбекам
        commits = db_stats.get('committed_transactions', 0)
        rollbacks = db_stats.get('rolled_back_transactions', 0)
        
        if commits + rollbacks > 0:
            rollback_ratio = rollbacks / (commits + rollbacks) * 100
            if rollback_ratio > 10:
                issues.append(f"Высокий процент роллбеков: {rollback_ratio:.1f}%")
                recommendations.append("Проверьте логику приложения на предмет частых роллбеков")
        
        return {
            'issues': issues,
            'recommendations': recommendations,
            'hit_ratio': hit_ratio if blocks_hit + blocks_read > 0 else 0,
            'rollback_ratio': rollback_ratio if commits + rollbacks > 0 else 0,
            'status': 'good' if not issues else 'needs_attention'
        }
    
    def _analyze_maintenance_issues(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Анализирует проблемы с обслуживанием"""
        issues = []
        recommendations = []
        
        table_stats = stats.get('table_stats', [])
        
        for table in table_stats:
            dead_tuples = table.get('dead_tuples', 0)
            live_tuples = table.get('live_tuples', 0)
            
            if live_tuples > 0:
                dead_ratio = dead_tuples / live_tuples * 100
                if dead_ratio > 20:
                    issues.append(f"Высокий процент мертвых кортежей в {table['tablename']}: {dead_ratio:.1f}%")
                    recommendations.append(f"Запустите VACUUM для таблицы {table['tablename']}")
        
        return {
            'issues': issues,
            'recommendations': recommendations,
            'status': 'good' if not issues else 'needs_attention'
        }
    
    def _generate_config_recommendations(self, settings: Dict[str, Any], system_info: Dict[str, Any], stats: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Генерирует рекомендации по конфигурации"""
        recommendations = []
        
        # Рекомендации по памяти
        shared_buffers = settings.get('shared_buffers', {}).get('value', '0')
        if shared_buffers and shared_buffers != '0':
            try:
                shared_buffers_mb = int(shared_buffers.replace('MB', '').replace('GB', ''))
                if shared_buffers_mb < 256:
                    recommendations.append({
                        'category': 'memory',
                        'setting': 'shared_buffers',
                        'current_value': shared_buffers,
                        'recommended_value': '256MB',
                        'priority': 'high',
                        'description': 'Увеличьте shared_buffers для улучшения производительности',
                        'impact': 'Улучшение кэширования данных в памяти'
                    })
            except ValueError:
                pass
        
        # Рекомендации по work_mem
        work_mem = settings.get('work_mem', {}).get('value', '0')
        if work_mem and work_mem != '0':
            try:
                work_mem_mb = int(work_mem.replace('MB', '').replace('kB', ''))
                if work_mem_mb < 8:
                    recommendations.append({
                        'category': 'memory',
                        'setting': 'work_mem',
                        'current_value': work_mem,
                        'recommended_value': '8MB',
                        'priority': 'medium',
                        'description': 'Увеличьте work_mem для улучшения сортировки и хэширования',
                        'impact': 'Ускорение операций сортировки и JOIN'
                    })
            except ValueError:
                pass
        
        # Рекомендации по логированию
        log_min_duration = settings.get('log_min_duration_statement', {}).get('value', '-1')
        if log_min_duration == '-1':
            recommendations.append({
                'category': 'monitoring',
                'setting': 'log_min_duration_statement',
                'current_value': 'disabled',
                'recommended_value': '1000ms',
                'priority': 'low',
                'description': 'Включите логирование медленных запросов',
                'impact': 'Возможность мониторинга производительности'
            })
        
        return recommendations
