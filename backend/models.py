from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

Role = Literal["DEALER", "EMPLOYEE"]
UserStatus = Literal["ACTIVE", "INACTIVE"]
CollectionStatus = Literal["PENDING", "PARTIALLY_COLLECTED", "COMPLETED"]
PaymentMethod = Literal["CASH", "BANK_TRANSFER", "UPI", "OTHER"]

class UserDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    name: str
    username: str
    phone: str
    role: Role
    status: UserStatus
    createdAt: str = Field(alias="createdAt")

class ClientDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    name: str
    phone: str
    address: str
    notes: Optional[str] = None
    createdAt: str = Field(alias="createdAt")

class ClientWithTotalsDTO(ClientDTO):
    totalAmount: float = Field(alias="totalAmount")
    receivedAmount: float = Field(alias="receivedAmount")
    remainingAmount: float = Field(alias="remainingAmount")

class CollectionDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    client: ClientDTO
    assignedEmployee: UserDTO = Field(alias="assignedEmployee")
    totalAmount: float = Field(alias="totalAmount")
    receivedAmount: float = Field(alias="receivedAmount")
    remainingAmount: float = Field(alias="remainingAmount")
    status: CollectionStatus
    collectionDate: str = Field(alias="collectionDate")
    dueDate: str = Field(alias="dueDate")
    notes: Optional[str] = None
    createdAt: str = Field(alias="createdAt")
    updatedAt: str = Field(alias="updatedAt")

class PaymentDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    collection: str
    client: ClientDTO
    employee: UserDTO
    amount: float
    paymentMethod: PaymentMethod = Field(alias="paymentMethod")
    remarks: Optional[str] = None
    paymentDate: str = Field(alias="paymentDate")
    createdAt: str = Field(alias="createdAt")
    verified: bool

class DashboardSummaryDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    totalAmount: float
    totalReceived: float
    totalRemaining: float
    pendingCount: int
    partiallyCollectedCount: int
    completedCount: int
    recentCollections: List[CollectionDTO]

class EmployeePerformanceDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    totalAssigned: float
    totalCollected: float
    pendingCount: int
    partiallyCollectedCount: int
    completedCount: int

class EmployeeDetailDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    employee: UserDTO
    performance: EmployeePerformanceDTO

class EmployeeBreakdownItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    employeeId: str
    employeeName: str
    totalCollected: float
    paymentCount: int

class StatusBreakdown(BaseModel):
    pending: int
    partiallyCollected: int
    completed: int

class PeriodReportDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    period: str
    totalCollected: float
    paymentCount: int
    employeeBreakdown: List[EmployeeBreakdownItem]
    statusBreakdown: StatusBreakdown

# Request Models
class LoginRequest(BaseModel):
    username: str
    password: str

class UpdateMeRequest(BaseModel):
    name: str
    username: Optional[str] = None

class ChangePasswordRequest(BaseModel):
    newPassword: str

class CreateDealerRequest(BaseModel):
    name: str
    phone: str
    username: str
    password: str

class CreateClientRequest(BaseModel):
    name: str
    phone: str
    address: str
    notes: Optional[str] = None

class UpdateClientRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None

class CreateEmployeeRequest(BaseModel):
    name: str
    phone: str
    username: str
    password: str

class UpdateEmployeeRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None

class CreateCollectionRequest(BaseModel):
    client: str
    assignedEmployee: str
    totalAmount: float
    collectionDate: str
    dueDate: str
    notes: Optional[str] = None

class UpdateCollectionRequest(BaseModel):
    assignedEmployee: Optional[str] = None
    totalAmount: Optional[float] = None
    collectionDate: Optional[str] = None
    dueDate: Optional[str] = None
    notes: Optional[str] = None

class CreatePaymentRequest(BaseModel):
    collection: str
    amount: float
    paymentMethod: PaymentMethod
    paymentDate: str
    remarks: Optional[str] = None

class UpdatePaymentRequest(BaseModel):
    amount: float
    paymentMethod: Optional[PaymentMethod] = None
    remarks: Optional[str] = None

class VerifyPaymentRequest(BaseModel):
    verified: bool
