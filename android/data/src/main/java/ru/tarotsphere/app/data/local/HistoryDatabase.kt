package ru.tarotsphere.app.data.local

import androidx.room.*
import kotlinx.coroutines.flow.Flow
import ru.tarotsphere.app.domain.model.HistoryItem

@Entity(tableName = "history", primaryKeys = ["owner", "id"])
data class HistoryEntity(
    val owner: String, val id: Long, val question: String, val type: String,
    val createdAt: String, val isFree: Boolean,
) {
    fun toDomain() = HistoryItem(id, type, question, createdAt, isFree)
}
@Entity(tableName = "reading_details", primaryKeys = ["owner", "id"])
data class ReadingEntity(val owner: String, val id: Long, val payload: String)
@Entity(tableName = "profiles")
data class ProfileEntity(@PrimaryKey val owner: String, val payload: String)

@Dao
interface HistoryDao {
    @Query("SELECT * FROM history WHERE owner = :owner ORDER BY id DESC")
    fun observe(owner: String): Flow<List<HistoryEntity>>
    @Upsert suspend fun saveHistory(rows: List<HistoryEntity>)
    @Upsert suspend fun saveDetail(row: ReadingEntity)
    @Upsert suspend fun saveProfile(row: ProfileEntity)
    @Query("SELECT * FROM reading_details WHERE owner = :owner AND id = :id")
    suspend fun detail(owner: String, id: Long): ReadingEntity?
    @Query("SELECT * FROM profiles WHERE owner = :owner")
    suspend fun profile(owner: String): ProfileEntity?
    @Query("DELETE FROM history") suspend fun clearHistory()
    @Query("DELETE FROM reading_details") suspend fun clearDetails()
    @Query("DELETE FROM profiles") suspend fun clearProfiles()
    @Transaction
    suspend fun clear() { clearHistory(); clearDetails(); clearProfiles() }
}

@Database(entities = [HistoryEntity::class, ReadingEntity::class, ProfileEntity::class], version = 1, exportSchema = true)
abstract class HistoryDatabase : RoomDatabase() {
    abstract fun historyDao(): HistoryDao
}
